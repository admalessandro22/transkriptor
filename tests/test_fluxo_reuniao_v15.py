# -*- coding: utf-8 -*-
"""FR-10.A4/FR-10.E4 — ciclo reunião -> fila -> texto posterior."""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from fila_processamento import FilaProcessamento


@pytest.fixture
def app_v15(tmp_path, monkeypatch, modulo_transkriptor):
    pasta = tmp_path / "transcricoes"
    audio = pasta / "audio"
    audio.mkdir(parents=True)
    argumentos = {}

    class TranscritorFalso:
        def __init__(self, **kwargs):
            argumentos.update(kwargs)
            self.rodando = False
            self.diarizando = False
            self.audios_preservados = []
            self.eventos_meet = []

        def start(self):
            self.rodando = True

        def stop(self):
            self.rodando = False
            base = pasta / "transcricao_2026-08-06_10h00"
            saida = base.with_suffix(".txt")
            saida.write_text("captura encerrada\n", encoding="utf-8")
            wav = audio / f"{base.name}_audio.wav"
            wav.write_bytes(b"RIFF" + b"\0" * 64)
            self.audios_preservados = [str(wav)]
            return str(saida)

    modulo_falso = types.ModuleType("transcricao_core")
    modulo_falso.Transcritor = TranscritorFalso
    monkeypatch.setitem(sys.modules, "transcricao_core", modulo_falso)
    monkeypatch.setattr(modulo_transkriptor, "PASTA_TRANSCRICOES", str(pasta))
    monkeypatch.setattr(modulo_transkriptor, "notificar", lambda *a, **k: None)
    watchdog = MagicMock()
    monkeypatch.setattr(modulo_transkriptor, "Watchdog", lambda *a, **k: watchdog)

    app = modulo_transkriptor.AppTranskriptor.__new__(
        modulo_transkriptor.AppTranskriptor
    )
    app.icone = None
    app.transcritor = None
    app.watchdog = None
    app.deteccao_ativa = True
    app.diarizacao_ativa = True
    app.capturar_mic = False
    app.identificar_minha_voz = False
    app.rotulo_usuario = "VOCÊ"
    app.criptografar_transcricoes = False
    app.modelo_whisper = "small"
    app.usar_nomes_meet = False
    app.modo_legendas_meet = False
    app.iniciar_com_windows = False
    app.detector = SimpleNamespace(
        reuniao_ativa=True,
        fontes_da_reuniao=["titulo"],
        instantaneo=lambda: [],
    )
    app.meet_bridge = SimpleNamespace(drenar_eventos=lambda: [])
    app._lock = threading.Lock()
    app._iniciando = False
    app._recusa_reuniao_ativa = False
    app._consentimento_em_andamento = False
    app._inicio_transcricao_wall_ms = None
    app._em_erro = False
    app._instante_erro = None
    app._estado_processamento = None
    app._worker_processamento = None
    app.fila = FilaProcessamento(str(pasta))
    app._pedir_consentimento = lambda: True
    app._em_thread = lambda alvo, _nome: alvo()
    app._status = MagicMock()
    app._atualizar_tooltip = MagicMock()
    app._erro_critico = MagicMock()
    app._despachar_proximo_job = MagicMock()
    app._argumentos_transcritor = argumentos
    return app


def test_fluxo_aceito_fecha_e_enfileira(app_v15):
    app_v15._processar_mudanca_meet("iniciou")

    assert app_v15._gravando() is True
    assert app_v15._argumentos_transcritor["processar_ao_vivo"] is False

    app_v15.detector.reuniao_ativa = False
    app_v15._processar_mudanca_meet("encerrou")

    assert app_v15._gravando() is False
    assert app_v15.transcritor is None
    assert app_v15.fila.quantidade("pending") == 1
    app_v15._despachar_proximo_job.assert_called_once_with()


def test_startup_recupera_job_interrompido(app_v15):
    audio = app_v15.fila.pasta_transcricoes / "audio" / "interrompido.wav"
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    job_id = app_v15.fila.enfileirar(str(audio), None, "interrompido", {})
    app_v15.fila.reivindicar(job_id)

    app_v15._preparar_processamento()

    assert app_v15.fila.obter(job_id).estado == "pending"
    app_v15._despachar_proximo_job.assert_called_once_with()


def test_menu_nao_oferece_captura_generica(app_v15):
    textos = [str(item) for item in app_v15._menu()]

    assert all("transcrição manual" not in texto.lower() for texto in textos)
    assert all("transcricao manual" not in texto.lower() for texto in textos)


def test_estado_pos_processamento_aparece_no_menu(app_v15):
    for estado in ("Em fila", "Processando", "Pronta", "Falhou"):
        app_v15._estado_processamento = estado
        assert estado in app_v15._texto_status()


def test_worker_que_falha_antes_do_claim_nao_entra_em_loop(app_v15):
    audio = app_v15.fila.pasta_transcricoes / "audio" / "worker-falho.wav"
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    job_id = app_v15.fila.enfileirar(str(audio), None, "worker-falho", {})
    worker = SimpleNamespace(wait=lambda: 1)
    app_v15._worker_processamento = worker

    app_v15._aguardar_worker(job_id, worker)

    assert app_v15._estado_processamento == "Falhou"
    assert app_v15.fila.obter(job_id).estado == "pending"
    app_v15._despachar_proximo_job.assert_not_called()
