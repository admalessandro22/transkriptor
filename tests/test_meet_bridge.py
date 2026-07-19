# -*- coding: utf-8 -*-
"""Testes da ponte WebSocket Meet (Fase 8 — FR-8.2)."""
import json
import queue
import threading
import time

import pytest

from meet_bridge import MeetBridge, normalizar_evento, sanitizar_nome_participante
from config import MAX_MENSAGEM_MEET_WS, MAX_NOME_PARTICIPANTE


def test_normalizar_evento_valido():
    ev = normalizar_evento({"nome": "Ana Silva", "ts_ms": 10500, "tipo": "ativo"})
    assert ev["nome"] == "Ana Silva"
    assert ev["ts_sec"] == pytest.approx(10.5)
    assert ev["tipo"] == "ativo"


def test_normalizar_evento_rejeita_sem_nome():
    assert normalizar_evento({"ts_ms": 1}) is None
    assert normalizar_evento("invalido") is None


def test_registrar_evento_na_fila():
    bridge = MeetBridge()
    bridge.registrar_evento({"nome": "Carlos", "ts_ms": 2000, "tipo": "ativo"})
    item = bridge.fila.get_nowait()
    assert item["nome"] == "Carlos"
    assert item["ts_sec"] == pytest.approx(2.0)


def test_drenar_eventos_esvazia_fila():
    bridge = MeetBridge()
    bridge.registrar_evento({"nome": "A", "ts_ms": 1000, "tipo": "ativo"})
    bridge.registrar_evento({"nome": "B", "ts_ms": 2000, "tipo": "lista"})
    drenado = bridge.drenar_eventos()
    assert len(drenado) == 2
    assert bridge.fila.empty()


def test_bridge_aceita_mensagem_json_string():
    bridge = MeetBridge()
    bridge.processar_mensagem(json.dumps({"nome": "João", "ts_ms": 5000, "tipo": "ativo"}))
    assert bridge.fila.get_nowait()["nome"] == "João"


def test_sanitizar_nome_remove_controle_e_trunca():
    nome = sanitizar_nome_participante("  Ana\x00Silva  " + "x" * 200)
    assert "\x00" not in nome
    assert len(nome) <= MAX_NOME_PARTICIPANTE
    assert nome.startswith("Ana")


def test_processar_mensagem_rejeita_payload_grande():
    bridge = MeetBridge()
    payload = "x" * (MAX_MENSAGEM_MEET_WS + 100)
    bridge.processar_mensagem(payload)
    assert bridge.fila.empty()
    valido = json.dumps({"nome": "A", "ts_ms": 1, "tipo": "ativo"})
    bridge.processar_mensagem(valido)
    assert not bridge.fila.empty()


def test_servidor_recebe_evento_via_websocket():
    pytest.importorskip("websockets")
    import asyncio
    import websockets

    from meet_bridge import iniciar_bridge_em_thread

    bridge = MeetBridge()
    porta = 5059
    thread = iniciar_bridge_em_thread(bridge, "127.0.0.1", porta)

    async def _enviar():
        uri = f"ws://127.0.0.1:{porta}?token={bridge.token}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"nome": "Ana", "ts_ms": 10500, "tipo": "ativo"}))

    asyncio.run(_enviar())
    time.sleep(0.3)
    eventos = bridge.drenar_eventos()
    bridge.parar()
    thread.join(timeout=2)
    assert len(eventos) == 1
    assert eventos[0]["nome"] == "Ana"