# -*- coding: utf-8 -*-
"""Ações sobre uma reunião na Central: excluir (dupla confirmação) e título.

- `GET  /api/reunioes/<id>/exclusao` → plano exato (itens, bytes, `plano_id`).
- `POST /api/reunioes/<id>/excluir` com `{plano_id, confirmacao: "EXCLUIR"}`:
  a 1ª confirmação é ver o plano; a 2ª é digitar EXCLUIR. Plano mudou → 409.
- `POST /api/reunioes/<id>/titulo` com `{titulo}` (vazio volta ao original).

Nomes de participantes continuam na rota de correção (`/correcao`), com
revisão e desfazer. Token, origem e JSON: `before_request` de `assistente.py`.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint("central_reunioes", __name__)
PALAVRA_CONFIRMACAO = "EXCLUIR"


def _raiz() -> Path:
    import assistente

    return Path(assistente.PASTA_TRANSCRICOES)


@bp.route("/api/reunioes/<meeting_id>/exclusao")
def api_plano_exclusao(meeting_id: str):
    import exclusao_reuniao as ex

    try:
        return jsonify(ex.planejar(_raiz(), meeting_id).como_dict())
    except ex.ReuniaoNaoEncontrada:
        return jsonify({"erro": "Reunião não encontrada"}), 404
    except ex.ExclusaoBloqueada:
        return jsonify({"erro": "A reunião ainda está sendo processada. Tente quando terminar."}), 409


@bp.route("/api/reunioes/<meeting_id>/excluir", methods=["POST"])
def api_excluir_reuniao(meeting_id: str):
    import exclusao_reuniao as ex

    dados = request.get_json(silent=True) or {}
    if dados.get("confirmacao") != PALAVRA_CONFIRMACAO or not isinstance(dados.get("plano_id"), str):
        return jsonify({"erro": f"Confirme digitando {PALAVRA_CONFIRMACAO}."}), 400
    try:
        plano = ex.excluir(_raiz(), meeting_id, dados["plano_id"])
    except ex.ReuniaoNaoEncontrada:
        return jsonify({"erro": "Reunião não encontrada"}), 404
    except ex.ExclusaoBloqueada:
        return jsonify({"erro": "A reunião ainda está sendo processada. Tente quando terminar."}), 409
    except ex.PlanoDivergente:
        return jsonify({"erro": "Os arquivos da reunião mudaram. Revise a lista e confirme de novo."}), 409
    except OSError:
        return jsonify({"erro": "Não foi possível excluir agora; nada foi apagado. Feche arquivos da reunião e tente de novo."}), 500
    return jsonify({"excluidos": len(plano.itens), "bytes": plano.bytes_total})


@bp.route("/api/reunioes/<meeting_id>/titulo", methods=["POST"])
def api_titulo_reuniao(meeting_id: str):
    from indice_transcricoes import definir_titulo

    dados = request.get_json(silent=True) or {}
    titulo = dados.get("titulo")
    if not isinstance(titulo, str):
        return jsonify({"erro": "Título inválido"}), 400
    try:
        return jsonify({"titulo": definir_titulo(_raiz() / "indice.json", meeting_id, titulo)})
    except ValueError:
        return jsonify({"erro": "O título pode ter até 80 caracteres."}), 400
    except KeyError:
        return jsonify({"erro": "Reunião não encontrada"}), 404
