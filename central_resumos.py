# -*- coding: utf-8 -*-
"""Resumo curto por reunião na Central (pedido do usuário, 24/09/2026).

`GET /api/reunioes/<id>/resumo` devolve `{estado: pronto, resumo}`, `{estado:
gerando}` (a geração entra na fila) ou `{estado: indisponivel, motivo}`.
`?tentar=1` limpa uma falha anterior (ex.: Ollama voltou). Token, origem e
JSON são exigidos pelo `before_request` de `assistente.py` para `/api/*`.
"""
from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint("central_resumos", __name__)

_servico = None
_servico_lock = threading.Lock()
_OCUPADO = ("gravando", "processando", "separando_vozes")
TIMEOUT_RESUMO_SEG = 300


def _modelos_instalados() -> list[str]:
    import config

    try:
        with urllib.request.urlopen(config.OLLAMA_URL.rstrip("/") + "/api/tags", timeout=config.OLLAMA_TIMEOUT_CONEXAO) as r:
            return [m["name"] for m in json.loads(r.read().decode("utf-8")).get("models", []) if m.get("name")]
    except Exception:  # noqa: BLE001 — Ollama fora do ar: sem modelo
        return []


def _app_ocupado() -> bool:
    """Gravando ou processando: o resumo espera para não disputar CPU/GPU."""
    import app_estado_ui

    provedor = app_estado_ui.provedor_atual()
    if provedor is None:
        return False
    try:
        snap = provedor()
    except Exception:  # noqa: BLE001
        return False
    return snap.estado in _OCUPADO or bool(snap.processamento)


def _contexto(modelo: str) -> int:
    import config
    from assistente_ollama import consultar_context_length

    return min(consultar_context_length(modelo) or 8192, config.OLLAMA_NUM_CTX_MAX)


def _chamar_resumo(modelo: str, mensagens: list[dict]) -> str:
    """Chamada própria: sem "thinking" (modelos como gemma4 passavam de 2 min só
    raciocinando), temperatura baixa e `num_ctx` igual ao orçamento usado."""
    import config

    corpo = {"model": modelo, "messages": mensagens, "stream": False, "think": False,
             "options": {"temperature": 0.2, "num_ctx": _contexto(modelo)}}
    req = urllib.request.Request(
        config.OLLAMA_URL.rstrip("/") + "/api/chat", data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_RESUMO_SEG) as r:
            return (json.loads(r.read().decode("utf-8")).get("message") or {}).get("content") or ""
    except Exception as exc:  # noqa: BLE001 — vira estado "indisponível", nunca resumo
        return f"[Erro ao contatar o Ollama: {type(exc).__name__}]"


def _orcamento(modelo: str) -> int:
    from assistente_ollama import orcamento_chars

    return orcamento_chars(_contexto(modelo))


def servico():
    global _servico
    with _servico_lock:
        if _servico is None:
            import assistente
            from resumo_reuniao import ServicoResumos

            _servico = ServicoResumos(
                Path(assistente.PASTA_TRANSCRICOES) / "resumos",
                carregar=lambda mid: assistente._carregar_resultado_reuniao(mid)[0],
                chamar=lambda modelo, mensagens: _chamar_resumo(modelo, mensagens),
                modelos=_modelos_instalados,
                ocupado=_app_ocupado,
                orcamento=_orcamento,
            )
        return _servico


@bp.route("/api/reunioes/<meeting_id>/resumo")
def api_resumo_reuniao(meeting_id: str):
    s = servico()
    if request.args.get("tentar") == "1":
        s.tentar_de_novo(meeting_id)
    return jsonify(s.obter(meeting_id))
