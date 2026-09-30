# -*- coding: utf-8 -*-
"""Configurações de IA da Central (T-15.D3 / UX-15.D3).

Transcrição (Whisper local: dispositivo e precisão), resumo e chat (Ollama
local ou OpenRouter, cada um com seu modelo). Vale mesmo sem a bandeja: tudo
fica em `config_user.json`. A chave do OpenRouter só entra (nunca volta), e
escolher o OpenRouter pela primeira vez responde 409 com o que sai do
computador até o usuário confirmar (SEC-15.D2).
"""
from __future__ import annotations

import time

from flask import Blueprint, jsonify, request

from config import IDIOMA

bp = Blueprint("central_ia", __name__)

PROVEDORES = ("ollama", "openrouter")
DISPOSITIVOS = ("auto", "cpu", "cuda")
PRECISOES = ("auto", "int8", "int8_float16", "float16")
MODELO_MAX = 120
_hardware_cache: tuple[bool, float] | None = None


def _hardware() -> tuple[bool, float]:
    global _hardware_cache
    if _hardware_cache is None:
        from config import detectar_cuda_e_vram

        _hardware_cache = detectar_cuda_e_vram()
    return _hardware_cache


def _estado() -> dict:
    import config_user
    import provedor_openrouter as po
    from config import resolver_modelo_whisper
    from provedores_ia import url_ollama

    cfg = config_user.carregar()
    cuda, vram = _hardware()
    return {
        "transcricao": {
            "dispositivo": cfg.get("whisper_dispositivo") or "auto",
            "precisao": cfg.get("whisper_precisao") or "auto",
            "idioma": IDIOMA,
            "hardware": {"cuda": bool(cuda), "vram_gb": round(float(vram), 1)},
            "recomendado": resolver_modelo_whisper(cuda, vram)[0],
        },
        **{funcao: {"provedor": cfg.get(f"ia_{funcao}_provedor") or "ollama",
                    "modelo": cfg.get(f"ia_{funcao}_modelo") or ""} for funcao in ("resumo", "chat")},
        "ollama_url": url_ollama(),
        "openrouter": {"configurada": po.chave() is not None, "final": po.chave_final(),
                       "consentido_em": cfg.get("openrouter_consentido_em")},
    }


def _provedor(nome: str):
    import provedor_openrouter as po
    from provedores_ia import ProvedorOllama

    if nome == "openrouter":
        return po.ProvedorOpenRouter(po.chave())
    return ProvedorOllama()


@bp.route("/api/ia")
def api_ia():
    return jsonify(_estado())


@bp.route("/api/ia/modelos")
def api_ia_modelos():
    from provedores_ia import ErroProvedor

    nome = request.args.get("provedor", "ollama")
    if nome not in PROVEDORES:
        return jsonify({"erro": "Provedor desconhecido"}), 400
    try:
        provedor = _provedor(nome)
    except ErroProvedor as exc:
        return jsonify({"estado": {"estado": exc.codigo, "detalhe": exc.mensagem_segura}, "modelos": []})
    estado = provedor.estado()
    modelos = provedor.listar_modelos() if estado.estado in ("online", "sem_modelos") else []
    return jsonify({
        "estado": {"estado": estado.estado, "detalhe": estado.detalhe, "versao": estado.versao},
        "modelos": [{"id": m.id, "nome": m.nome, "contexto": m.contexto, "local": m.local} for m in modelos],
    })


def _consentimento_pendente():
    from provedor_openrouter import TEXTO_CONSENTIMENTO

    return jsonify({"erro": "Confirmação necessária", "acao": "openrouter", "titulo": "Usar o OpenRouter?",
                    "consequencia": TEXTO_CONSENTIMENTO, "confirmar": "Usar o OpenRouter"}), 409


def _aplicar(chave: str, valor, confirmado: bool):
    import config_user
    import provedor_openrouter as po
    from provedores_ia import normalizar_url_ollama

    invalido = (jsonify({"erro": "Valor inválido"}), 400)
    if chave == "whisper_dispositivo":
        return config_user.atualizar(whisper_dispositivo=valor) if valor in DISPOSITIVOS else invalido
    if chave == "whisper_precisao":
        return config_user.atualizar(whisper_precisao=valor) if valor in PRECISOES else invalido
    if chave == "ollama_url":
        try:
            return config_user.atualizar(ollama_url=normalizar_url_ollama(str(valor or "")))
        except ValueError:
            return jsonify({"erro": "O Ollama só pode ser usado neste computador (127.0.0.1 ou localhost)."}), 400
    if chave in ("ia_resumo_provedor", "ia_chat_provedor"):
        if valor not in PROVEDORES:
            return invalido
        if valor == "openrouter" and not config_user.carregar().get("openrouter_consentido_em"):
            if not confirmado:
                return _consentimento_pendente()
            po.consentir()
        return config_user.atualizar(**{chave: valor})
    if chave in ("ia_resumo_modelo", "ia_chat_modelo"):
        texto = str(valor or "").strip()
        if len(texto) > MODELO_MAX or any(ord(c) < 32 for c in texto):
            return invalido
        return config_user.atualizar(**{chave: texto})
    if chave == "openrouter_chave":
        try:
            return po.salvar_chave(str(valor or ""))
        except ValueError:
            return invalido
    if chave == "openrouter_consentimento":
        if valor is True:
            return po.consentir() if confirmado else _consentimento_pendente()
        if valor is False:  # revogar: nada mais sai do computador
            cfg = config_user.carregar()
            cfg.pop("openrouter_consentido_em", None)
            cfg.update(ia_resumo_provedor="ollama", ia_chat_provedor="ollama")
            return config_user.salvar(cfg)
        return invalido
    return jsonify({"erro": "Chave desconhecida"}), 400


@bp.route("/api/ia", methods=["POST"])
def api_ia_post():
    dados = request.get_json(silent=True) or {}
    resposta = _aplicar(str(dados.get("chave", "")), dados.get("valor"), dados.get("confirmado") is True)
    if isinstance(resposta, tuple):
        return resposta
    return jsonify(_estado())


@bp.route("/api/ia/testar", methods=["POST"])
def api_ia_testar():
    """Prompt fixo e curto: nenhuma transcrição sai para testar."""
    from provedores_ia import ErroProvedor

    dados = request.get_json(silent=True) or {}
    nome, modelo = dados.get("provedor"), str(dados.get("modelo") or "").strip()
    if nome not in PROVEDORES or not modelo or len(modelo) > MODELO_MAX:
        return jsonify({"erro": "Informe provedor e modelo"}), 400
    inicio = time.monotonic()
    try:
        _provedor(nome).conversar([{"role": "user", "content": "Responda apenas: ok"}], modelo=modelo,
                                  opcoes={"temperature": 0}, timeout=60)
    except ErroProvedor as exc:
        return jsonify({"ok": False, "erro": exc.mensagem_segura})
    return jsonify({"ok": True, "latencia_ms": int((time.monotonic() - inicio) * 1000)})
