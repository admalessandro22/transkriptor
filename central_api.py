# -*- coding: utf-8 -*-
"""Ações da Central que dependem do aplicativo da bandeja (SDD v1.9).

O Flask roda no mesmo processo da bandeja quando aberto pelo menu; a bandeja
registra provedores aqui. Sem provedor, cada ação responde 404/503 explicando
o que falta, nunca finge sucesso. Token, origem e JSON são exigidos pelo
`before_request` de `assistente.py` para todas as rotas `/api/*`.
"""
from __future__ import annotations

import re
from typing import Callable, Mapping

from flask import Blueprint, jsonify, request

from config import ARQUIVO_VOZES_CONHECIDAS, MAX_NOME_PARTICIPANTE
from politica_privacidade import ProtectionUnavailable

bp = Blueprint("central_api", __name__)

_PROVEDOR_CENTROIDES: Callable[[], Mapping | None] | None = None
_ROTULO = re.compile(r"^FALANTE_\d{2}$")


def registrar_provedor_centroides(fn: Callable[[], Mapping | None] | None) -> None:
    """A bandeja registra como obter os centroides da última separação de vozes."""
    global _PROVEDOR_CENTROIDES
    _PROVEDOR_CENTROIDES = fn


def centroides_atuais() -> Mapping | None:
    if _PROVEDOR_CENTROIDES is None:
        return None
    try:
        return _PROVEDOR_CENTROIDES()
    except Exception:  # noqa: BLE001 — a Central nunca cai por causa da bandeja
        return None


@bp.route("/api/estado")
def api_estado():
    """FR-14.D1: snapshot da bandeja sem lock e sem dados sensíveis; 503 sem provedor."""
    import app_estado_ui

    provedor = app_estado_ui.provedor_atual()
    if provedor is None:
        return jsonify({"erro": "estado indisponível: o aplicativo da bandeja não está ligado a esta Central"}), 503
    try:
        snap = provedor()
    except Exception:  # noqa: BLE001 — a Central nunca cai por causa da bandeja
        return jsonify({"erro": "estado indisponível"}), 503
    return jsonify(snap.como_dict())


@bp.route("/api/acoes/aprender-voz", methods=["POST"])
def api_aprender_voz():
    """UX-14.C3: ação separada e explícita; a correção por reunião nunca chega aqui."""
    from renomear_falante_flow import persistir_renomeacao_falante

    dados = request.get_json(silent=True) or {}
    rotulo = str(dados.get("rotulo", "")).strip().upper()
    nome = str(dados.get("nome", "")).strip()
    if not _ROTULO.match(rotulo):
        return jsonify({"erro": "Falante inválido"}), 400
    if len(nome) < 2 or len(nome) > MAX_NOME_PARTICIPANTE:
        return jsonify({"erro": "Nome inválido"}), 400
    centroides = centroides_atuais()
    if not centroides:
        return jsonify({"erro": "Nenhuma separação de vozes recente para aprender. Processe uma reunião com separação de vozes e tente de novo."}), 404
    if rotulo not in centroides:
        return jsonify({"erro": "Este falante não está na última separação de vozes."}), 404
    try:
        salvo = persistir_renomeacao_falante(rotulo, nome, centroides, ARQUIVO_VOZES_CONHECIDAS)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    except ProtectionUnavailable:
        # DU-15/SEC-13.E1: sem cifra, biometria não é salva em claro; falha visível, nunca sucesso.
        return jsonify({"erro": "Proteção indisponível: a voz não é salva sem a chave de cifra. Ative a proteção no aplicativo e tente de novo."}), 503
    return jsonify({"salvo": salvo})
