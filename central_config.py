# -*- coding: utf-8 -*-
"""Configurações da Central (FR-14.D2): espelham os toggles da bandeja.

Cada mutação reutiliza a mesma função do menu (`app_bandeja_menu`), com as
mesmas regras e persistência; ações sensíveis exigem `confirmado: true` e
respondem 409 com a consequência de `confirmacoes.py` até lá. Sem bandeja
registrada, tudo responde 503 explicando o motivo.
"""
from __future__ import annotations

from typing import Callable

from flask import Blueprint, jsonify, request

from config import ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC, MODELOS_WHISPER_MENU
from confirmacoes import consequencia

bp = Blueprint("central_config", __name__)

_APP = None
CHAVES = (
    "deteccao_ativa", "diarizacao_ativa", "identificar_minha_voz", "usar_nomes_meet",
    "modo_legendas_meet", "criptografar_transcricoes", "protection_mode", "modelo_whisper",
    "iniciar_com_windows", "apagar_perfil_voz",
)
BOOLEANAS = ("deteccao_ativa", "diarizacao_ativa", "identificar_minha_voz", "usar_nomes_meet", "modo_legendas_meet", "criptografar_transcricoes", "iniciar_com_windows")


def registrar_app(app) -> None:
    global _APP
    _APP = app


def app_registrado():
    return _APP


def _perfil_existe() -> bool:
    try:
        from crypto_storage import perfil_existe

        return bool(perfil_existe(ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC))
    except Exception:  # noqa: BLE001
        return False


def _protecao() -> str:
    try:
        from politica_privacidade import modo_efetivo

        return str(modo_efetivo().value)
    except Exception:  # noqa: BLE001
        return "compatible"


def estado_config(app) -> dict:
    return {
        "deteccao_ativa": bool(getattr(app, "deteccao_ativa", True)),
        "diarizacao_ativa": bool(getattr(app, "diarizacao_ativa", True)),
        "identificar_minha_voz": bool(getattr(app, "identificar_minha_voz", False)),
        "usar_nomes_meet": bool(getattr(app, "usar_nomes_meet", False)),
        "modo_legendas_meet": bool(getattr(app, "modo_legendas_meet", False)),
        "criptografar_transcricoes": bool(getattr(app, "criptografar_transcricoes", True)),
        "protection_mode": _protecao(),
        "modelo_whisper": str(getattr(app, "modelo_whisper", "auto")),
        "iniciar_com_windows": bool(getattr(app, "iniciar_com_windows", False)),
        "perfil_voz_existe": _perfil_existe(),
        "modelos_whisper": list(MODELOS_WHISPER_MENU),
    }


def _exige_confirmacao(chave: str, valor) -> str | None:
    if chave == "deteccao_ativa" and valor is False:
        return "pausar_gravacao"
    if chave == "protection_mode":
        return "modo_protegido"
    if chave == "apagar_perfil_voz":
        return "apagar_perfil_voz"
    return None


def aplicar(app, chave: str, valor, confirmar: Callable[[], bool]) -> tuple[dict | None, tuple | None]:
    """Aplica uma chave pela mesma função do menu. Devolve (estado, erro)."""
    atual = estado_config(app)
    if chave in BOOLEANAS:
        if not isinstance(valor, bool):
            return None, ({"erro": "Valor inválido"}, 400)
        alternar = {
            "deteccao_ativa": lambda: app.alternar_deteccao(confirmar=confirmar),
            "diarizacao_ativa": app.alternar_diarizacao,
            "identificar_minha_voz": app.alternar_identificar_voz,
            "usar_nomes_meet": app.alternar_nomes_meet,
            "modo_legendas_meet": app.alternar_legendas_meet,
            "criptografar_transcricoes": app.alternar_criptografia,
            "iniciar_com_windows": app.alternar_startup,
        }[chave]
        if atual[chave] != valor:
            alternar()
    elif chave == "modelo_whisper":
        if valor not in MODELOS_WHISPER_MENU:
            return None, ({"erro": "Modelo inválido"}, 400)
        app.definir_modelo_whisper(None, valor)
    elif chave == "protection_mode":
        if valor != "protected":
            return None, ({"erro": "Só é possível ativar o modo protegido; ele não é desativado pela Central"}, 400)
        app.ativar_modo_protegido(confirmar=confirmar)
    elif chave == "apagar_perfil_voz":
        app.apagar_perfil_voz()
    return estado_config(app), None


@bp.route("/api/config")
def api_config_get():
    if _APP is None:
        return jsonify({"erro": "configurações indisponíveis: o aplicativo da bandeja não está ligado a esta Central"}), 503
    return jsonify(estado_config(_APP))


@bp.route("/api/config", methods=["POST"])
def api_config_post():
    if _APP is None:
        return jsonify({"erro": "configurações indisponíveis: o aplicativo da bandeja não está ligado a esta Central"}), 503
    dados = request.get_json(silent=True) or {}
    chave = str(dados.get("chave", ""))
    if chave not in CHAVES:
        return jsonify({"erro": "Chave desconhecida"}), 400
    valor = dados.get("valor")
    confirmado = dados.get("confirmado") is True
    acao = _exige_confirmacao(chave, valor)
    if acao and not confirmado:
        textos = consequencia(acao)
        return jsonify({"erro": "Confirmação necessária", "acao": acao, **textos}), 409
    estado, erro = aplicar(_APP, chave, valor, confirmar=lambda: True)
    if erro:
        corpo, codigo = erro
        return jsonify(corpo), codigo
    return jsonify(estado)
