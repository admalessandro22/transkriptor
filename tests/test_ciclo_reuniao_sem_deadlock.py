# -*- coding: utf-8 -*-
"""FR-10.A4/FR-10.C1 — o ciclo de reunião nunca pode travar a bandeja.

Regressão de 2026-08-07: `_iniciar_transcricao` segurava `self._lock` enquanto
chamava `Transcritor.start()`, e `start()` chama `on_status` — que é `_status`,
que pedia o mesmo `threading.Lock` não reentrante. O app ficou vivo por três
dias sem gravar um único frame e sem uma linha no log.

Os dublês daqui **têm de** chamar `on_status` de dentro de `start()`/`stop()`,
na thread chamadora e numa thread filha, exatamente como o `Transcritor` real
(`transcricao_core.py`: `on_status("Gravação da reunião em andamento.")` e
`on_status("Capturando audio...")`). Um dublê que só faz `self.rodando = True`
não exercita nada.
"""
from __future__ import annotations

import sys
import threading
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app_ciclo_reuniao

from fila_processamento import FilaProcessamento

LIMITE_SEG = 10.0


class TranscritorQueFalaNoStart:
    """Espelha a sequência real de `on_status` do Transcritor."""

    def __init__(self, **kwargs):
        self.on_status = kwargs["on_status"]
        self.rodando = False
        self.diarizando = False
        self.finalizando = False
        self.audios_preservados = []
        self.eventos_meet = []
        self.capturou = threading.Event()
        self._parar = threading.Event()

    def start(self):
        self.rodando = True
        self._thread = threading.Thread(target=self._capturar, daemon=True)
        self._thread.start()
        # transcricao_core.Transcritor.start, modo posterior
        self.on_status("Gravação da reunião em andamento.")

    def _capturar(self):
        # transcricao_core.Transcritor._capturar, antes de abrir o dispositivo
        self.on_status("Capturando audio... (16000 Hz)")
        self.capturou.set()
        self._parar.wait(LIMITE_SEG)

    def stop(self):
        self._parar.set()
        self.rodando = False
        self.on_status("Transcrição encerrada.")
        return None


def _executar_com_limite(alvo):
    """Roda `alvo` numa thread e devolve se ele terminou dentro do limite."""
    terminou = threading.Event()

    def _rodar():
        alvo()
        terminou.set()

    threading.Thread(target=_rodar, daemon=True).start()
    return terminou.wait(LIMITE_SEG)


@pytest.fixture
def app_real_status(tmp_path, monkeypatch, modulo_transkriptor):
    """App com `_status` verdadeiro — é ele que disputa o lock."""
    pasta = tmp_path / "transcricoes"
    (pasta / "audio").mkdir(parents=True)

    modulo_falso = types.ModuleType("transcricao_core")
    modulo_falso.Transcritor = TranscritorQueFalaNoStart
    monkeypatch.setitem(sys.modules, "transcricao_core", modulo_falso)
    monkeypatch.setattr(app_ciclo_reuniao, "PASTA_TRANSCRICOES", str(pasta))
    monkeypatch.setattr(app_ciclo_reuniao, "notificar", lambda *a, **k: None)
    monkeypatch.setattr(app_ciclo_reuniao, "Watchdog", lambda *a, **k: MagicMock())
    monkeypatch.setattr(app_ciclo_reuniao, "perfil_existe", lambda *a, **k: False)

    app = modulo_transkriptor.AppTranskriptor.__new__(
        modulo_transkriptor.AppTranskriptor
    )
    app.icone = None
    app.transcritor = None
    app.watchdog = None
    app.deteccao_ativa = True
    app.diarizacao_ativa = False
    app.capturar_mic = False
    app.identificar_minha_voz = False
    app.rotulo_usuario = "VOCÊ"
    app.criptografar_transcricoes = False
    app.modelo_whisper = "small"
    app.usar_nomes_meet = False
    app.modo_legendas_meet = False
    app.detector = SimpleNamespace(
        reuniao_ativa=True, fontes_da_reuniao=["titulo"], instantaneo=lambda: []
    )
    app.meet_bridge = SimpleNamespace(drenar_eventos=lambda: [])
    app._lock = modulo_transkriptor.threading.Lock()
    app._iniciando = False
    app._recusa_reuniao_ativa = False
    app._consentimento_em_andamento = False
    app._inicio_transcricao_wall_ms = None
    app._em_erro = False
    app._instante_erro = None
    app._estado_processamento = None
    app._worker_processamento = None
    app._ultimo_job_id = None
    app.ultimo_log = ""
    app.fila = FilaProcessamento(str(pasta))
    app._pedir_consentimento = lambda: True
    app._em_thread = lambda alvo, _nome: alvo()
    app._atualizar_tooltip = lambda: None
    app._enfileirar_reuniao = MagicMock()
    return app


def test_iniciar_transcricao_nao_trava_com_start_que_reporta_status(app_real_status):
    """FR-10.C1: `start()` que chama `on_status` não pode travar o chamador."""
    assert _executar_com_limite(app_real_status._iniciar_transcricao), (
        "_iniciar_transcricao não retornou: deadlock em _status sob self._lock"
    )
    assert app_real_status._gravando() is True


def test_thread_de_captura_nao_fica_presa_no_status(app_real_status):
    """A captura reportava status antes de abrir o áudio — e travava lá."""
    _executar_com_limite(app_real_status._iniciar_transcricao)

    transcritor = app_real_status.transcritor
    assert transcritor is not None and transcritor.capturou.wait(LIMITE_SEG), (
        "thread de captura ficou presa em _status; nenhum frame seria gravado"
    )


def test_ciclo_completo_iniciar_e_encerrar_nao_trava(app_real_status):
    """FR-10.D1: encerrar a reunião fecha a captura e libera a bandeja."""
    assert _executar_com_limite(
        lambda: app_real_status._processar_mudanca_meet("iniciou")
    ), "início da reunião travou"
    transcritor = app_real_status.transcritor
    assert transcritor is not None and transcritor.capturou.wait(LIMITE_SEG)

    app_real_status.detector.reuniao_ativa = False
    assert _executar_com_limite(
        lambda: app_real_status._processar_mudanca_meet("encerrou")
    ), "encerramento travou: foi aqui que o log parou em 2026-08-08"

    assert app_real_status.transcritor is None
    app_real_status._enfileirar_reuniao.assert_not_called()  # stop() devolveu None


def test_portao_de_consentimento_e_liberado_apos_o_ciclo(app_real_status):
    """Um travamento não pode cegar as reuniões seguintes (FR-10.B3)."""
    _executar_com_limite(lambda: app_real_status._processar_mudanca_meet("iniciou"))

    assert app_real_status._consentimento_em_andamento is False


def test_status_nunca_bloqueia_quando_o_lock_do_app_esta_tomado(app_real_status):
    """`_status` é chamado de threads de áudio; não pode depender de `self._lock`."""
    with app_real_status._lock:
        assert _executar_com_limite(
            lambda: app_real_status._status("Capturando audio... (16000 Hz)")
        ), "_status ficou preso no lock do app"
