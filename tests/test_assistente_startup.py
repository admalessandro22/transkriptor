# -*- coding: utf-8 -*-
"""Testes de startup do assistente Flask (Fase 1 — FR-1.1/1.2)."""
import socket
import threading

from assistente import aguardar_servidor, app, iniciar_servidor_em_thread


def _porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_servidor_thread_fica_vivo():
    porta = _porta_livre()
    thread = iniciar_servidor_em_thread(app, "127.0.0.1", porta)
    try:
        assert thread.is_alive()
        assert thread.daemon is True
    finally:
        pass


def test_aguardar_servidor_detecta_resposta():
    porta = _porta_livre()
    url = f"http://127.0.0.1:{porta}"
    thread = iniciar_servidor_em_thread(app, "127.0.0.1", porta)
    try:
        assert aguardar_servidor(url, timeout=10, intervalo=0.5) is True
        assert thread.is_alive()
    finally:
        pass


def test_aguardar_servidor_timeout_sem_servidor():
    porta = _porta_livre()
    url = f"http://127.0.0.1:{porta}"
    assert aguardar_servidor(url, timeout=1, intervalo=0.3) is False


def test_iniciar_servidor_retorna_thread():
    porta = _porta_livre()
    thread = iniciar_servidor_em_thread(app, "127.0.0.1", porta)
    assert isinstance(thread, threading.Thread)