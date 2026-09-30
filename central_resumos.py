# -*- coding: utf-8 -*-
"""Resumo curto por reunião na Central (pedido do usuário, 24/09/2026).

`GET /api/reunioes/<id>/resumo` devolve `{estado: pronto, resumo}`, `{estado:
gerando}` (a geração entra na fila) ou `{estado: indisponivel, motivo}`.
`?tentar=1` limpa uma falha anterior (ex.: Ollama voltou); `?gerar=1` gera
para reunião anterior aos resumos automáticos (`{estado: sem_resumo}`). Token, origem e
JSON são exigidos pelo `before_request` de `assistente.py` para `/api/*`.
"""
from __future__ import annotations

import threading
from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint("central_resumos", __name__)

_servico = None
_servico_lock = threading.Lock()
_OCUPADO = ("gravando", "processando", "separando_vozes")
_PROCESSANDO = ("Processando", "Em fila")
# Resumo automático só para reuniões que começam a partir daqui (decisão do
# usuário, 24/09/2026); as anteriores só com "Gerar resumo agora".
RESUMOS_AUTOMATICOS_DESDE = "2026-09-24T18:40:00-03:00"
TIMEOUT_RESUMO_SEG = 300


def _modelos_instalados() -> list[str]:
    from provedores_ia import provedor_ollama  # T-15.D1

    return [m.id for m in provedor_ollama().listar_modelos()]


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
    # "Pronta"/"Falhou"/"Cancelada" ficam no campo depois de terminar: não é ocupado.
    return snap.estado in _OCUPADO or snap.processamento in _PROCESSANDO


def _contexto(modelo: str) -> int:
    import config
    from assistente_ollama import consultar_context_length

    return min(consultar_context_length(modelo) or 8192, config.OLLAMA_NUM_CTX_MAX)


def _chamar_resumo(modelo: str, mensagens: list[dict]) -> str:
    """Chamada própria: sem "thinking" (modelos como gemma4 passavam de 2 min só
    raciocinando), temperatura baixa e `num_ctx` igual ao orçamento usado."""
    from provedores_ia import ErroProvedor, provedor_ollama

    try:
        return provedor_ollama().conversar(
            mensagens, modelo=modelo, opcoes={"temperature": 0.2, "num_ctx": _contexto(modelo)},
            pensar=False, timeout=TIMEOUT_RESUMO_SEG)
    except ErroProvedor as exc:  # vira estado "indisponível", nunca resumo
        return f"[{exc.mensagem_segura}]"


def _orcamento(modelo: str) -> int:
    from assistente_ollama import orcamento_chars

    return orcamento_chars(_contexto(modelo))


def _elegivel(raiz: Path, meeting_id: str) -> bool:
    from indice_transcricoes import _carregar_indice, _instante

    entrada = _carregar_indice(Path(raiz) / "indice.json").get(meeting_id)
    inicio = entrada.get("started_at") if isinstance(entrada, dict) else None
    return bool(inicio) and _instante(inicio) >= _instante(RESUMOS_AUTOMATICOS_DESDE)


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
                elegivel=lambda mid: _elegivel(Path(assistente.PASTA_TRANSCRICOES), mid),
            )
        return _servico


def agendar_concluida(job) -> None:
    """Agenda uma reunião nova ao concluir o job, mesmo sem a Central aberta."""
    from indice_transcricoes import _instante

    metadados = getattr(job, "metadados", None) or {}
    inicio = metadados.get("inicio_iso") if isinstance(metadados, dict) else None
    if (getattr(job, "estado", None) == "ready" and inicio
            and _instante(inicio) >= _instante(RESUMOS_AUTOMATICOS_DESDE)):
        servico().obter(job.id, gerar=True)


@bp.route("/api/reunioes/<meeting_id>/resumo")
def api_resumo_reuniao(meeting_id: str):
    s = servico()
    if request.args.get("tentar") == "1":
        s.tentar_de_novo(meeting_id)
    return jsonify(s.obter(meeting_id, gerar=request.args.get("gerar") == "1"))
