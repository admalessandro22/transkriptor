# -*- coding: utf-8 -*-
"""Testes de reserva de porta Meet bridge vs assistente."""
from config import PORTA_MEET_BRIDGE, PORTAS_FALLBACK


def test_portas_fallback_nao_inclui_meet_bridge():
    assert PORTA_MEET_BRIDGE not in PORTAS_FALLBACK


def test_porta_livre_nao_tenta_meet_bridge(monkeypatch):
    from assistente import porta_livre

    tentativas = []

    class Sock:
        def bind(self, addr):
            tentativas.append(addr[1])
            raise OSError("ocupada")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("assistente.socket.socket", lambda *a, **k: Sock())
    try:
        porta_livre()
    except RuntimeError:
        pass
    assert PORTA_MEET_BRIDGE not in tentativas