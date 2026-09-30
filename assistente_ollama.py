# -*- coding: utf-8 -*-
"""Cliente Ollama e orçamento de contexto do assistente (FR-4.*)."""

from __future__ import annotations

from flask import Response, jsonify

import config as _config
from provedores_ia import ErroProvedor, provedor_ollama

_cache_ctx: dict[str, int] = {}


def tamanho_mensagens(mensagens) -> int:
    """Soma chars de role+content para contabilidade de orçamento (F2)."""
    total = 0
    for msg in mensagens or []:
        if not isinstance(msg, dict):
            continue
        total += len(str(msg.get("role") or "")) + len(str(msg.get("content") or ""))
    return total


def orcamento_chars(context_length: int) -> int:
    """FR-4.2: ~75% do contexto em chars (3.2 chars/token PT)."""
    n = min(int(context_length or 0), _config.OLLAMA_NUM_CTX_MAX)
    if n <= 0:
        return _config.MAX_CHARS_TRANSCRICAO
    return max(1000, int(int(n * 0.75) * _config.CHARS_POR_TOKEN_PT))


def consultar_context_length(modelo: str) -> int | None:
    """Janela de contexto do modelo pelo provedor; None se falhar (fallback)."""
    if modelo in _cache_ctx:
        return _cache_ctx[modelo]
    contexto = provedor_ollama().contexto(modelo)
    if contexto:
        _cache_ctx[modelo] = contexto
    return contexto


def chamar_ollama_sync(
    modelo: str, mensagens: list[dict], num_ctx: int | None = None
) -> str:
    try:
        return provedor_ollama().conversar(mensagens, modelo=modelo, opcoes={"num_ctx": num_ctx} if num_ctx else None)
    except ErroProvedor as e:
        return f"[{e.mensagem_segura}]"


def stream_chat(modelo: str, mensagens: list[dict], num_ctx: int | None = None) -> Response:
    """Resposta em stream pelo provedor (T-15.D1); falha vira texto, nunca 500."""

    def stream():
        try:
            yield from provedor_ollama().conversar_stream(
                mensagens, modelo=modelo, opcoes={"num_ctx": num_ctx} if num_ctx else None)
        except GeneratorExit:
            raise
        except Exception as e:
            yield (
                "\n[Não foi possível contatar o Ollama. "
                f"Verifique se está em execução. ({type(e).__name__})]"
            )

    return Response(stream(), mimetype="text/plain; charset=utf-8")


def processar_chat(
    modelo: str,
    transcricao: str,
    pergunta: str,
    historico: list,
    *,
    orcamento_fn=None,
    ctx_fn=None,
    sync_fn=None,
    max_chars=None,
):
    """Monta resposta de /api/chat (streaming ou map-reduce)."""
    orcamento_fn = orcamento_fn or orcamento_chars
    ctx_fn = ctx_fn or consultar_context_length
    sync_fn = sync_fn or chamar_ollama_sync
    limite = _config.MAX_CHARS_TRANSCRICAO if max_chars is None else max_chars

    if not str(transcricao or "").strip():
        return "Sem evidência na transcrição para responder."
    pergunta = str(pergunta or "")

    ctx = ctx_fn(modelo)
    if ctx:
        orcamento = orcamento_fn(ctx)
        num_ctx = min(ctx, _config.OLLAMA_NUM_CTX_MAX)
    else:
        orcamento = limite
        num_ctx = None

    historico = [m for m in (historico or []) if isinstance(m, dict)]
    while historico and tamanho_mensagens(historico) + len(pergunta) > orcamento:
        historico.pop(0)

    if len(transcricao) > orcamento:
        from resumo_longo import dividir_em_blocos, responder_longo

        blocos = dividir_em_blocos(transcricao, orcamento)

        def stream_longo():
            yield f"[Reunião longa: resposta consolidada de {len(blocos)} blocos]\n"
            try:
                yield responder_longo(
                    modelo,
                    blocos,
                    pergunta,
                    lambda m, msgs: sync_fn(m, msgs, num_ctx=num_ctx),
                )
            except Exception as e:
                yield f"\n[Erro ao processar reunião longa: {e}]"

        return Response(
            stream_longo(),
            mimetype="text/plain; charset=utf-8",
            headers={"X-Transkriptor-Truncada": "true"},
        )

    system = (
        "Você é um assistente especializado em analisar reuniões. "
        "Use a transcrição abaixo como contexto para responder às perguntas do usuário. "
        "Responda sempre em português, de forma clara e organizada. "
        "Se a informação não estiver na transcrição, diga que não há dados suficientes.\n\n"
        f"=== TRANSCRIÇÃO ===\n{transcricao}\n=== FIM ==="
    )
    mensagens = [{"role": "system", "content": system}]
    for msg in historico[-_config.MAX_HISTORICO_CHAT :]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            mensagens.append({"role": msg["role"], "content": msg["content"]})
    mensagens.append({"role": "user", "content": pergunta})

    return stream_chat(modelo, mensagens, num_ctx)
