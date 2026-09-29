# -*- coding: utf-8 -*-
"""T-15.A2 / FR-15.A2 — relógio da extensão convertido para o tempo do áudio."""
from __future__ import annotations

import random

import pytest

import relogio_meet
from relogio_meet import AmostraRelogio, eventos_no_tempo_do_audio, melhor_offset, para_monotonic_servidor_ns

MS = 1_000_000  # ns por ms


def _amostra(n, envio_ms, ida_ms, volta_ms, desvio_cliente_ms, base_mono_ms=10_000.0, base_wall_ms=1_789_848_000_000.0):
    """Ping enviado pelo servidor em envio_ms; cliente responde com o próprio relógio."""
    chegada_cliente_wall = base_wall_ms + envio_ms + ida_ms + desvio_cliente_ms
    return AmostraRelogio(
        n=n,
        envio_mono_ns=int((base_mono_ms + envio_ms) * MS),
        envio_wall_ns=int((base_wall_ms + envio_ms) * MS),
        recebido_mono_ns=int((base_mono_ms + envio_ms + ida_ms + volta_ms) * MS),
        cliente_wall_ms=chegada_cliente_wall,
    )


def test_sem_amostra_relogio_incerto():
    assert melhor_offset([]) is None


def test_menor_rtt_define_offset():
    amostras = [
        _amostra(1, 0, 40, 40, desvio_cliente_ms=25),   # RTT 80, assimétrica ruim
        _amostra(2, 100, 2, 2, desvio_cliente_ms=25),   # RTT 4: a melhor
        _amostra(3, 200, 30, 5, desvio_cliente_ms=25),
    ]
    offset_ms, _ = melhor_offset(amostras)
    assert offset_ms == pytest.approx(25.0, abs=0.01)


def test_incerteza_meia_rtt():
    _, incerteza = melhor_offset([_amostra(1, 0, 3, 3, desvio_cliente_ms=0)])
    assert incerteza == pytest.approx(3.0 + relogio_meet.RESOLUCAO_RELOGIO_MS)


def test_amostra_com_rtt_negativo_ignorada():
    ruim = AmostraRelogio(n=1, envio_mono_ns=10 * MS, envio_wall_ns=0, recebido_mono_ns=5 * MS, cliente_wall_ms=0.0)
    assert melhor_offset([ruim]) is None


def test_offset_simulado_com_jitter_erra_pouco():
    """Aceite: cliente 37 ms adiantado, jitter de até 10 ms por perna, 5 trocas."""
    sorteio = random.Random(1509)
    amostras = [
        _amostra(n, n * 200.0, sorteio.uniform(0.2, 10), sorteio.uniform(0.2, 10), desvio_cliente_ms=37)
        for n in range(5)
    ]
    offset_ms, incerteza = melhor_offset(amostras)
    assert abs(offset_ms - 37) <= 15
    assert incerteza <= relogio_meet.INCERTEZA_TEMPO_MAX_MS


def test_conversao_pagina_para_monotonic_do_servidor():
    # Página: fala começou 1500 ms antes do "agora" da página.
    page_wall_ms = 1_789_848_060_000.0
    page_perf_ms = page_wall_ms + 3.0          # timeOrigin da página 3 ms adiantado
    t_fala_pagina = page_perf_ms - 1500.0
    agora_wall_ns = int(page_wall_ms * MS) - 20 * MS  # cliente 20 ms adiantado
    agora_mono_ns = 50_000 * MS
    ns = para_monotonic_servidor_ns(
        t_fala_pagina, page_perf_ms=page_perf_ms, page_wall_ms=page_wall_ms,
        offset_ms=20.0, agora_mono_ns=agora_mono_ns, agora_wall_ns=agora_wall_ns,
    )
    assert ns == pytest.approx(agora_mono_ns - 1500 * MS, abs=MS // 1000)


def test_conversao_para_ms_audio():
    primeiro = 40_000 * MS
    eventos = [
        {"kind": "caption", "speech_started_monotonic_ns": 52_500 * MS, "clock_uncertainty_ms": 4.0},
        {"kind": "caption", "speech_started_monotonic_ns": 61_000 * MS, "clock_uncertainty_ms": 9.0},
        {"kind": "caption", "client_wall_ms": 1_789_848_060_000},
    ]
    convertidos, incerteza = eventos_no_tempo_do_audio(eventos, primeiro)
    assert convertidos[0]["ts_sec"] == pytest.approx(12.5)
    assert convertidos[1]["ts_sec"] == pytest.approx(21.0)
    assert "ts_sec" not in convertidos[2]
    assert incerteza == pytest.approx(9.0)
    assert "ts_sec" not in eventos[0]  # não altera a entrada


def test_sem_primeiro_frame_nao_converte():
    eventos = [{"kind": "caption", "speech_started_monotonic_ns": 1, "clock_uncertainty_ms": 1.0}]
    convertidos, incerteza = eventos_no_tempo_do_audio(eventos, None)
    assert "ts_sec" not in convertidos[0]
    assert incerteza is None


def test_fala_antes_do_primeiro_frame_fica_fora():
    """Fala anterior ao início do áudio não pode virar tempo negativo."""
    eventos = [{"kind": "caption", "speech_started_monotonic_ns": 1 * MS, "clock_uncertainty_ms": 1.0}]
    convertidos, _ = eventos_no_tempo_do_audio(eventos, 5_000 * MS)
    assert "ts_sec" not in convertidos[0]


# ---------------------------------------------------------------- ponte ----

def _ponte_com_sessao(tmp_path):
    from eventos_meet_store import EventStore
    from meet_bridge import MeetBridge
    from sessao_reuniao import criar_sessao

    bridge = MeetBridge()
    sessao = criar_sessao("chave-opaca", "2026-09-19T20:00:00Z", "padrao")
    store = EventStore(tmp_path / "eventos", sessao)
    bridge.registrar_hello({"tipo": "hello", "connection_id": "c1", "tab_id": "aba-1",
                            "meeting_hint": "abc-defg-hij", "active": True})
    bridge.definir_sessao_ativa(sessao, store, meeting_hint="abc-defg-hij")
    bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")
    return bridge, sessao, store


def _legenda_v2(sessao, **extra):
    ev = {"schema_version": 2, "event_id": "e1", "session_id": sessao.session_id,
          "connection_id": "c1", "seq": 0, "tab_id": "aba-1", "meeting_key": sessao.meeting_key,
          "kind": "caption", "client_wall_ms": 1_789_848_060_000, "client_monotonic_ms": 1000,
          "received_monotonic_ns": 1, "text": "fala sintética",
          "caption_started_ms": 1_789_848_058_500.0, "caption_last_ms": 1_789_848_059_000.0}
    ev.update(extra)
    return ev


def test_ponte_ping_pong_define_relogio_da_conexao(chave_teste, tmp_path):
    bridge, _, _ = _ponte_com_sessao(tmp_path)
    assert bridge.relogios.relogio_de("c1") is None
    ping = bridge.relogios.iniciar_ping("c1")
    assert ping["tipo"] == "relogio_ping" and ping["connection_id"] == "c1"
    bridge.relogios.registrar_pong("c1", ping["n"], cliente_wall_ms=relogio_meet.agora_wall_ms())
    offset_ms, incerteza = bridge.relogios.relogio_de("c1")
    assert abs(offset_ms) < 50
    assert incerteza < 50


def test_ponte_recusa_pong_desconhecido(chave_teste, tmp_path):
    bridge, _, _ = _ponte_com_sessao(tmp_path)
    bridge.relogios.registrar_pong("c1", 999, cliente_wall_ms=1.0)
    bridge.relogios.registrar_pong("c9", 0, cliente_wall_ms=1.0)
    assert bridge.relogios.relogio_de("c1") is None


def test_ponte_carimba_fala_no_relogio_monotonic(chave_teste, tmp_path):
    bridge, sessao, store = _ponte_com_sessao(tmp_path)
    ping = bridge.relogios.iniciar_ping("c1")
    bridge.relogios.registrar_pong("c1", ping["n"], cliente_wall_ms=relogio_meet.agora_wall_ms())
    agora = relogio_meet.agora_wall_ms()
    ev = _legenda_v2(sessao, caption_started_ms=agora - 2000.0, caption_last_ms=agora - 500.0,
                     page_perf_ms=agora, page_wall_ms=agora)
    bridge.registrar_envelope("c1", ev)
    gravado = list(store.read_events())[0]
    assert gravado["speech_last_monotonic_ns"] - gravado["speech_started_monotonic_ns"] == pytest.approx(
        1500 * MS, abs=2 * MS)
    assert gravado["received_monotonic_ns"] - gravado["speech_started_monotonic_ns"] == pytest.approx(
        2000 * MS, abs=60 * MS)
    assert 0 < gravado["clock_uncertainty_ms"] < 50


def test_ponte_sem_relogio_nao_carimba(chave_teste, tmp_path):
    bridge, sessao, store = _ponte_com_sessao(tmp_path)
    agora = relogio_meet.agora_wall_ms()
    bridge.registrar_envelope("c1", _legenda_v2(sessao, page_perf_ms=agora, page_wall_ms=agora))
    gravado = list(store.read_events())[0]
    assert "speech_started_monotonic_ns" not in gravado


def test_cliente_nao_forja_campos_do_servidor(chave_teste, tmp_path):
    bridge, sessao, store = _ponte_com_sessao(tmp_path)
    ev = _legenda_v2(sessao, speech_started_monotonic_ns=123, clock_uncertainty_ms=0.0)
    bridge.registrar_envelope("c1", ev)
    gravado = list(store.read_events())[0]
    assert "speech_started_monotonic_ns" not in gravado
    assert "clock_uncertainty_ms" not in gravado


def test_ping_pong_pelo_websocket_real(chave_teste, tmp_path):
    """Ponte pinga após vincular a aba; o pong do cliente define o relógio."""
    import asyncio
    import json

    import websockets

    from config import RELOGIO_PINGS_INICIAIS
    from eventos_meet_store import EventStore
    from meet_bridge import MeetBridge, iniciar_bridge_em_thread
    from sessao_reuniao import criar_sessao

    bridge = MeetBridge(token="token-sintetico")
    sessao = criar_sessao("chave-opaca", "2026-09-19T20:00:00Z", "padrao")
    store = EventStore(tmp_path / "eventos", sessao)
    thread = iniciar_bridge_em_thread(bridge, "127.0.0.1", 5083)

    async def exercitar():
        async with websockets.connect("ws://127.0.0.1:5083?token=token-sintetico",
                                      origin="http://127.0.0.1:5083") as ws:
            hello = {"tipo": "hello", "connection_id": "c1", "tab_id": "aba-1",
                     "meeting_hint": "abc-defg-hij", "active": True}
            await ws.send(json.dumps(hello))
            await asyncio.sleep(0.1)
            bridge.definir_sessao_ativa(sessao, store, meeting_hint="abc-defg-hij")
            await ws.send(json.dumps(hello))
            respondidos = 0
            while respondidos < RELOGIO_PINGS_INICIAIS:
                msg = json.loads(await asyncio.wait_for(ws.recv(), 3))
                if msg.get("tipo") != "relogio_ping":
                    continue
                await ws.send(json.dumps({"tipo": "relogio_pong", "n": msg["n"], "connection_id": "c1",
                                          "client_wall_ms": relogio_meet.agora_wall_ms()}))
                respondidos += 1
            await asyncio.sleep(0.1)
            vistos.append(bridge.relogios.relogio_de("c1"))
        await asyncio.sleep(0.2)
        vistos.append(bridge.relogios.relogio_de("c1"))  # socket fechado: esquecido

    vistos = []
    try:
        asyncio.run(exercitar())
        assert vistos[0] is not None
        offset_ms, incerteza = vistos[0]
        assert abs(offset_ms) < 50 and incerteza < 50
        assert vistos[1] is None
    finally:
        bridge.parar()
        thread.join(timeout=2)
