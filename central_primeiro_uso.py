# -*- coding: utf-8 -*-
"""Assistente de primeiro uso (T-15.E3 / FR-15.E3).

Hardware e modelo Whisper recomendado; Ollama detectado (online, parado ou
ausente) com os modelos já instalados no seletor, download do modelo sugerido
pelo hardware (DP-15-11) com progresso, "Iniciar Ollama" com confirmação e a
página oficial quando falta instalar; estado da extensão. Nunca devolve o
caminho do executável (tem o nome do usuário).
"""
from __future__ import annotations

import re
import subprocess
import threading
import uuid

from flask import Blueprint, jsonify, request

bp = Blueprint("central_primeiro_uso", __name__)

PAGINA_OLLAMA = "https://ollama.com/download"
# DP-15-11: leve para máquina modesta; maior com GPU ≥ 8 GB ou RAM ≥ 32 GB.
MODELO_LEVE = {"id": "granite4.1:3b", "tamanho_gb": 2.0}
MODELO_MAIOR = {"id": "gemma4:latest", "tamanho_gb": 8.9}
_NOME_MODELO = re.compile(r"[a-z0-9][a-z0-9._-]{0,50}(:[a-z0-9._-]{1,28})?")
_downloads: dict[str, dict] = {}
_lock = threading.Lock()


def _ram_gb() -> float:
    try:
        import ctypes

        class _Memoria(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        memoria = _Memoria()
        memoria.dwLength = ctypes.sizeof(_Memoria)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memoria))
        return memoria.ullTotalPhys / 1024 ** 3
    except Exception:  # noqa: BLE001
        return 0.0


def modelo_sugerido(*, ram_gb: float, cuda: bool, vram_gb: float) -> dict:
    grande = (cuda and vram_gb >= 8.0) or ram_gb >= 32.0
    return dict(MODELO_MAIOR if grande else MODELO_LEVE)


def _detectar():
    from detector_ollama import detectar_ollama

    return detectar_ollama()


def _lancar(executavel: str) -> None:
    """Abre o Ollama já instalado (o app da bandeja, se existir; senão `serve`)."""
    import os

    pasta = os.path.dirname(executavel)
    app_bandeja = os.path.join(pasta, "ollama app.exe")
    comando = [app_bandeja] if os.path.isfile(app_bandeja) else [executavel, "serve"]
    sem_janela = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(comando, creationflags=sem_janela, close_fds=True)  # noqa: S603 — caminho detectado, sem shell


def _extensao_pareada() -> bool:
    import central_config

    pareador = getattr(getattr(central_config.app_registrado(), "meet_bridge", None), "pareador", None)
    return bool(pareador is not None and pareador.tem_credencial())


@bp.route("/api/primeiro-uso")
def api_primeiro_uso():
    import config_user
    from central_ia import _hardware
    from config import resolver_modelo_whisper

    cuda, vram = _hardware()
    deteccao = _detectar()
    return jsonify({
        "hardware": {"cuda": bool(cuda), "vram_gb": round(float(vram), 1), "ram_gb": round(_ram_gb(), 1)},
        "whisper_recomendado": resolver_modelo_whisper(cuda, vram)[0],
        "ollama": {"estado": deteccao.estado, "versao": deteccao.versao, "pagina_instalacao": PAGINA_OLLAMA,
                   "modelos": [{"id": m.id, "tamanho_bytes": m.tamanho_bytes} for m in deteccao.modelos]},
        "modelo_sugerido": modelo_sugerido(ram_gb=_ram_gb(), cuda=cuda, vram_gb=vram),
        "extensao": {"pareada": _extensao_pareada()},
        "concluido": bool(config_user.carregar().get("assistente_inicial_concluido")),
    })


def _baixar(id_: str, modelo: str) -> None:
    from provedores_ia import ErroProvedor, ProvedorOllama, baixar_modelo

    try:
        for passo in baixar_modelo(ProvedorOllama(), modelo):
            with _lock:
                estado = _downloads[id_]
                if isinstance(passo.get("total"), int) and passo["total"] > 0:
                    estado["percentual"] = int(100 * (passo.get("completed") or 0) / passo["total"])
                if passo.get("status") == "success":
                    estado.update(estado="concluido", percentual=100)
                if passo.get("error"):
                    estado.update(estado="falhou", erro="O Ollama recusou o download.")
    except ErroProvedor as exc:
        with _lock:
            _downloads[id_].update(estado="falhou", erro=exc.mensagem_segura)
    with _lock:
        if _downloads[id_]["estado"] == "baixando":
            _downloads[id_].update(estado="falhou", erro="O download terminou sem confirmação.")


@bp.route("/api/primeiro-uso/ollama/baixar", methods=["POST"])
def api_baixar():
    modelo = str((request.get_json(silent=True) or {}).get("modelo") or "")
    if not _NOME_MODELO.fullmatch(modelo):
        return jsonify({"erro": "Nome de modelo inválido"}), 400
    id_ = uuid.uuid4().hex
    with _lock:
        _downloads[id_] = {"modelo": modelo, "estado": "baixando", "percentual": 0}
    threading.Thread(target=_baixar, args=(id_, modelo), daemon=True, name="Transkriptor-BaixarModelo").start()
    return jsonify({"id": id_}), 202


@bp.route("/api/primeiro-uso/ollama/baixar/<id_>")
def api_baixar_estado(id_: str):
    with _lock:
        estado = dict(_downloads.get(id_) or {})
    return (jsonify(estado), 200) if estado else (jsonify({"erro": "Download desconhecido"}), 404)


@bp.route("/api/primeiro-uso/ollama/iniciar", methods=["POST"])
def api_iniciar_ollama():
    deteccao = _detectar()
    if deteccao.estado != "parado" or not deteccao.executavel:
        return jsonify({"erro": "Não há Ollama parado para iniciar neste computador."}), 400
    if (request.get_json(silent=True) or {}).get("confirmado") is not True:
        return jsonify({"erro": "Confirmação necessária", "titulo": "Iniciar o Ollama?",
                        "consequencia": "O Ollama instalado neste computador será aberto em segundo plano.",
                        "confirmar": "Iniciar"}), 409
    _lancar(deteccao.executavel)
    return jsonify({"iniciado": True}), 202


@bp.route("/api/primeiro-uso/concluir", methods=["POST"])
def api_concluir():
    import config_user

    config_user.atualizar(assistente_inicial_concluido=True)
    return jsonify({"concluido": True})
