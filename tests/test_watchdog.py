# -*- coding: utf-8 -*-
"""Testes do watchdog de threads (NFR-1)."""
import threading
import time
from unittest.mock import MagicMock

from watchdog import Watchdog


class _TranscritorFake:
    def __init__(self, cap_viva=True, proc_viva=True):
        self.rodando = True
        self._thread_cap = MagicMock()
        self._thread_cap.is_alive = MagicMock(return_value=cap_viva)
        self._thread_proc = MagicMock()
        self._thread_proc.is_alive = MagicMock(return_value=proc_viva)
        self._reiniciar_captura = MagicMock()
        self._reiniciar_processar = MagicMock()


def test_watchdog_reinicia_captura_morta():
    t = _TranscritorFake(cap_viva=False, proc_viva=True)
    status_msgs = []
    w = Watchdog(t, on_status=status_msgs.append, intervalo=0.05)
    w._verificar()
    t._reiniciar_captura.assert_called_once()
    assert any("captura" in m for m in status_msgs)


def test_watchdog_reinicia_processamento_morto():
    t = _TranscritorFake(cap_viva=True, proc_viva=False)
    status_msgs = []
    w = Watchdog(t, on_status=status_msgs.append, intervalo=0.05)
    w._verificar()
    t._reiniciar_processar.assert_called_once()
    assert any("processamento" in m for m in status_msgs)


def test_watchdog_erro_critico_apos_limite_reinicios(monkeypatch):
    monkeypatch.setattr("watchdog.LIMITE_REINICIOS", 2)
    t = _TranscritorFake(cap_viva=False, proc_viva=True)
    erros = []
    w = Watchdog(t, on_erro_critico=erros.append, intervalo=0.05)
    w._verificar()
    w._verificar()
    w._verificar()
    assert len(erros) == 1
    assert "Captura" in erros[0]


def test_watchdog_loop_para_quando_stop():
    t = _TranscritorFake()
    w = Watchdog(t, intervalo=0.05)
    w.start()
    time.sleep(0.15)
    w.stop()
    assert not w._thread.is_alive()