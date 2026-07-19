# -*- coding: utf-8 -*-
"""Testes de segurança da ponte Meet (token, fila limitada)."""
import json

import pytest

from config import MAX_FILA_MEET_WS
from meet_bridge import MeetBridge, origem_permitida, token_url_valido


def test_fila_limitada_descarta_excesso():
    bridge = MeetBridge(token="segredo", max_fila=3)
    for i in range(5):
        bridge.registrar_evento({"nome": f"P{i}", "ts_ms": i, "tipo": "ativo"})
    assert bridge.fila.qsize() == 3


def test_registrar_evento_respeita_max_fila_config():
    bridge = MeetBridge(token="x", max_fila=MAX_FILA_MEET_WS)
    assert bridge.fila.maxsize == MAX_FILA_MEET_WS


def test_token_url_valido():
    assert token_url_valido("abc", "abc") is True
    assert token_url_valido("abc", "xyz") is False
    assert token_url_valido(None, "abc") is False


def test_origem_permitida_chrome_extension():
    assert origem_permitida("chrome-extension://abcdefghijklmnop") is True
    assert origem_permitida("http://127.0.0.1:5050") is True
    assert origem_permitida("https://evil.example.com") is False


def test_servidor_rejeita_token_invalido():
    pytest.importorskip("websockets")
    import asyncio
    import time

    from meet_bridge import iniciar_bridge_em_thread

    bridge = MeetBridge(token="token-correto")
    porta = 5061
    thread = iniciar_bridge_em_thread(bridge, "127.0.0.1", porta)

    async def _tentar():
        import websockets

        uri = f"ws://127.0.0.1:{porta}?token=errado"
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({"nome": "Ana", "ts_ms": 1, "tipo": "ativo"}))
        except Exception:
            pass

    asyncio.run(_tentar())
    time.sleep(0.3)
    assert bridge.drenar_eventos() == []
    bridge.parar()
    thread.join(timeout=2)


def test_servidor_aceita_token_valido():
    pytest.importorskip("websockets")
    import asyncio
    import time

    from meet_bridge import iniciar_bridge_em_thread

    bridge = MeetBridge(token="token-ok")
    porta = 5062
    thread = iniciar_bridge_em_thread(bridge, "127.0.0.1", porta)

    async def _enviar():
        import websockets

        uri = f"ws://127.0.0.1:{porta}?token=token-ok"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"nome": "Ana", "ts_ms": 10500, "tipo": "ativo"}))

    asyncio.run(_enviar())
    time.sleep(0.3)
    eventos = bridge.drenar_eventos()
    bridge.parar()
    thread.join(timeout=2)
    assert len(eventos) == 1
    assert eventos[0]["nome"] == "Ana"