# -*- coding: utf-8 -*-
"""Ações locais da Central (SDD v1.9).

O estado da bandeja depende de um provedor. Aprender voz usa somente a reunião
escolhida e seu áudio validado, mesmo após reiniciar a bandeja. Token, origem e
JSON são exigidos pelo `before_request` de `assistente.py` para `/api/*`.
"""
from __future__ import annotations

import re

from flask import Blueprint, jsonify, request

from config import ARQUIVO_VOZES_CONHECIDAS, MAX_NOME_PARTICIPANTE, PASTA_TRANSCRICOES
from politica_privacidade import ProtectionUnavailable

bp = Blueprint("central_api", __name__)

_ROTULO = re.compile(r"^FALANTE_\d{2}$")


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
    meeting_id = str(dados.get("meeting_id", "")).strip()
    expected_revision = str(dados.get("expected_revision", "")).strip()
    if not _ROTULO.match(rotulo):
        return jsonify({"erro": "Falante inválido"}), 400
    if len(nome) < 2 or len(nome) > MAX_NOME_PARTICIPANTE:
        return jsonify({"erro": "Nome inválido"}), 400
    from central_resumos import _app_ocupado
    from crypto_storage import ErroDescriptografia

    if _app_ocupado():
        return jsonify({"erro": "Aguarde terminar a gravação ou o processamento para aprender a voz."}), 409
    try:
        from aprendizado_voz_reuniao import AprendizadoIndisponivel, embedding_da_reuniao

        embedding = embedding_da_reuniao(
            meeting_id, rotulo, expected_revision, raiz=PASTA_TRANSCRICOES,
        )
        salvo = persistir_renomeacao_falante(
            rotulo, nome, {rotulo: embedding}, ARQUIVO_VOZES_CONHECIDAS,
        )
    except AprendizadoIndisponivel as exc:
        return jsonify({"erro": str(exc)}), exc.status
    except ErroDescriptografia:
        return jsonify({"erro": "Não foi possível abrir o áudio protegido desta reunião."}), 503
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    except ProtectionUnavailable:
        # DU-15/SEC-13.E1: sem cifra, biometria não é salva em claro; falha visível, nunca sucesso.
        return jsonify({"erro": "Proteção indisponível: a voz não é salva sem a chave de cifra. Ative a proteção no aplicativo e tente de novo."}), 503
    return jsonify({"salvo": salvo})
