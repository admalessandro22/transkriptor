# -*- coding: utf-8 -*-
"""Cliente Ollama e orçamento de contexto do assistente (FR-4.*)."""

from __future__ import annotations

import json
import urllib.request

from flask import Response, jsonify

import config as _config

_cache_ctx: dict[str, int] = {}


def _ollama_url() -> str:
    return _config.OLLAMA_URL


def orcamento_chars(context_length: int) -> int:
    """FR-4.2: ~75% do contexto em chars (3.2 chars/token PT)."""
    n = min(int(context_length or 0), _config.OLLAMA_NUM_CTX_MAX)
    if n <= 0:
        return _config.MAX_CHARS_TRANSCRICAO
    return max(1000, int(int(n * 0.75) * _config.CHARS_POR_TOKEN_PT))


def consultar_context_length(modelo: str) -> int | None:
    """Consulta /api/show; None se falhar (fallback)."""
    if modelo in _cache_ctx:
        return _cache_ctx[modelo]
    try:
        payload = json.dumps({"name": modelo}).encode("utf-8")
        req = urllib.request.Request(
            _ollama_url().rstrip("/") + "/api/show",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_config.OLLAMA_TIMEOUT_LEITURA) as r:
            dados = json.loads(r.read().decode("utf-8"))
        info = dados.get("model_info") or {}
        for k, v in info.items():
            if "context_length" in str(k).lower() and isinstance(v, (int, float)):
                _cache_ctx[modelo] = int(v)
                return _cache_ctx[modelo]
        for part in str(dados.get("parameters") or "").split():
            if part.isdigit() and int(part) >= 512:
                _cache_ctx[modelo] = int(part)
                return _cache_ctx[modelo]
    except Exception:
        return None
    return None


def chamar_ollama_sync(
    modelo: str, mensagens: list[dict], num_ctx: int | None = None
) -> str:
    body = {"model": modelo, "messages": mensagens, "stream": False}
    if num_ctx:
        body["options"] = {"num_ctx": num_ctx}
    req = urllib.request.Request(
        _ollama_url().rstrip("/") + "/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_config.OLLAMA_TIMEOUT_LEITURA) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        return (dados.get("message") or {}).get("content") or ""
    except Exception as e:
        return f"[Erro ao contatar o Ollama: {e}]"


def stream_chat_ollama(req) -> Response:
    def stream():
        try:
            with urllib.request.urlopen(
                req, timeout=_config.OLLAMA_TIMEOUT_LEITURA
            ) as resp:
                for linha in resp:
                    linha = linha.decode("utf-8").strip()
                    if not linha:
                        continue
                    try:
                        bloco = json.loads(linha)
                        conteudo = bloco.get("message", {}).get("content", "")
                        if conteudo:
                            yield conteudo
                        if bloco.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            yield (
                "\n[Não foi possível contatar o Ollama. "
                f"Verifique se está em execução. ({e})]"
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

    ctx = ctx_fn(modelo)
    if ctx:
        orcamento = orcamento_fn(ctx)
        num_ctx = min(ctx, _config.OLLAMA_NUM_CTX_MAX)
    else:
        orcamento = limite
        num_ctx = None

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

    body = {"model": modelo, "messages": mensagens, "stream": True}
    if num_ctx:
        body["options"] = {"num_ctx": num_ctx}
    req = urllib.request.Request(
        _ollama_url().rstrip("/") + "/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return stream_chat_ollama(req)
