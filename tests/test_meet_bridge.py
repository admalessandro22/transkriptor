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


def test_envelope_v1_sem_sessao_nao_cai_na_fila_legada():
    bridge = MeetBridge()
    bridge.registrar_evento({"schema_version": 1, "event_id": "e1", "nome": "Pessoa Sintética", "tipo": "ativo"})
    assert bridge.fila.empty()


def test_hello_vincula_somente_hint_ativo_unico(chave_teste, tmp_path):
    from eventos_meet_store import EventStore
    from sessao_reuniao import EnvelopeRejeitado, criar_sessao

    bridge = MeetBridge()
    bridge.registrar_hello({"tipo": "hello", "connection_id": "c1", "tab_id": "aba-1", "meeting_hint": "abc-defg-hij", "active": True})
    assert bridge.hint_ativo_unico() == "abc-defg-hij"
    sessao = criar_sessao("chave-opaca", "2026-09-19T20:00:00Z", "padrao")
    store = EventStore(tmp_path / "eventos", sessao)
    bridge.definir_sessao_ativa(sessao, store, meeting_hint="abc-defg-hij")
    resposta = bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")
    assert resposta == {"tipo": "sessao", "connection_id": "c1", "tab_id": "aba-1", "session_id": sessao.session_id, "meeting_key": sessao.meeting_key}
    with pytest.raises(EnvelopeRejeitado):
        bridge.iniciar_conexao_logica("c2", "aba-2", 1_789_848_060_000, meeting_hint="outra-sala")
    bridge.registrar_hello({"tipo": "hello", "connection_id": "c2", "tab_id": "aba-2", "meeting_hint": "xyz-abcd-efg", "active": True})
    assert bridge.hint_ativo_unico() is None


def test_ack_v1_so_apos_evento_duravel_e_relogio_do_servidor(chave_teste, tmp_path):
    from eventos_meet_store import EventStore
    from sessao_reuniao import criar_sessao

    bridge = MeetBridge()
    sessao = criar_sessao("chave-opaca", "2026-09-19T20:00:00Z", "padrao")
    store = EventStore(tmp_path / "eventos", sessao)
    bridge.registrar_hello({"tipo": "hello", "connection_id": "c1", "tab_id": "aba-1", "meeting_hint": "abc-defg-hij", "active": True})
    bridge.definir_sessao_ativa(sessao, store, meeting_hint="abc-defg-hij")
    bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")
    evento = {"schema_version": 1, "event_id": "e1", "session_id": sessao.session_id,
              "connection_id": "c1", "seq": 0, "tab_id": "aba-1", "meeting_key": sessao.meeting_key,
              "kind": "caption", "client_wall_ms": 1_789_848_060_000,
              "client_monotonic_ms": 1000, "received_monotonic_ns": 1,
              "text": "fala sintética"}
    assert bridge.registrar_envelope("c1", evento) == 0
    gravados = list(store.read_events())
    assert len(gravados) == 1
    assert gravados[0]["received_monotonic_ns"] != 1
    assert gravados[0]["received_monotonic_ns"] > 0
    assert gravados[0]["text"] == "fala sintética"


def test_websocket_hello_sessao_ack_no_mesmo_socket(chave_teste, tmp_path):
    import asyncio
    import websockets
    from eventos_meet_store import EventStore
    from meet_bridge import iniciar_bridge_em_thread
    from sessao_reuniao import criar_sessao

    bridge = MeetBridge(token="token-sintetico")
    sessao = criar_sessao("chave-opaca", "2026-09-19T20:00:00Z", "padrao")
    store = EventStore(tmp_path / "eventos", sessao)
    thread = iniciar_bridge_em_thread(bridge, "127.0.0.1", 5081)

    async def exercitar():
        async with websockets.connect("ws://127.0.0.1:5081?token=token-sintetico", origin="http://127.0.0.1:5081") as ws:
            hello = {"tipo": "hello", "connection_id": "c1", "tab_id": "aba-1",
                     "meeting_hint": "abc-defg-hij", "active": True, "client_wall_ms": 1_789_848_060_000,
                     "client_monotonic_ms": 1000}
            await ws.send(json.dumps(hello))
            await asyncio.sleep(0.1)
            bridge.definir_sessao_ativa(sessao, store, meeting_hint="abc-defg-hij")
            await ws.send(json.dumps(hello))
            resposta = json.loads(await asyncio.wait_for(ws.recv(), 2))
            assert resposta["tipo"] == "sessao"
            evento = {"schema_version": 1, "event_id": "e1", "session_id": sessao.session_id,
                      "connection_id": "c1", "seq": 0, "tab_id": "aba-1", "meeting_key": sessao.meeting_key,
                      "kind": "caption", "client_wall_ms": 1_789_848_060_000,
                      "client_monotonic_ms": 1001, "text": "fala sintética"}
            await ws.send(json.dumps(evento))
            assert json.loads(await asyncio.wait_for(ws.recv(), 2)) == {"tipo": "ack", "connection_id": "c1", "seq": 0}
            segundo_hello = {**hello, "connection_id": "c2", "tab_id": "aba-2"}
            await ws.send(json.dumps(segundo_hello))
            segunda_sessao = json.loads(await asyncio.wait_for(ws.recv(), 2))
            assert segunda_sessao["connection_id"] == "c2"
            await ws.send(json.dumps({**evento, "connection_id": "c2", "tab_id": "aba-2", "event_id": "e2"}))
            assert json.loads(await asyncio.wait_for(ws.recv(), 2)) == {"tipo": "ack", "connection_id": "c2", "seq": 0}

    try:
        asyncio.run(exercitar())
        reaberto = EventStore(tmp_path / "eventos", sessao)
        assert [e["event_id"] for e in reaberto.read_events()] == ["e1", "e2"]
    finally:
        bridge.parar()
        thread.join(timeout=2)


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
        async with websockets.connect(uri, origin=f"http://127.0.0.1:{porta}") as ws:
            await ws.send(json.dumps({"nome": "Ana", "ts_ms": 10500, "tipo": "ativo"}))

    asyncio.run(_enviar())
    time.sleep(0.3)
    eventos = bridge.drenar_eventos()
    bridge.parar()
    thread.join(timeout=2)
    assert len(eventos) == 1
    assert eventos[0]["nome"] == "Ana"
