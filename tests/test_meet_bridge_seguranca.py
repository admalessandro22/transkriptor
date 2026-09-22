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


def test_prefixo_localhost_nao_autoriza_dominio_externo():
    assert origem_permitida("http://localhost.example.test") is False


def test_listener_producao_rejeita_origin_ausente():
    assert origem_permitida(None) is False


def test_origem_extensao_exige_id_valido():
    assert origem_permitida("chrome-extension://abcdefghijklmnopabcdefghijklmnop") is True
    assert origem_permitida("chrome-extension://evil") is False
    assert origem_permitida("chrome-extension://abcdefghijklmnop.evil.test") is False


def _servidor_teste(bridge, porta):
    from meet_bridge import iniciar_bridge_em_thread

    thread = iniciar_bridge_em_thread(bridge, "127.0.0.1", porta)
    return thread


def test_convite_uso_unico_e_token_antigo_rejeitado():
    pytest.importorskip("websockets")
    import asyncio
    import time

    from meet_bridge import ConviteInvalido, MeetBridge, Pareador

    pareador = Pareador()
    bridge = MeetBridge(pareador=pareador)
    thread = _servidor_teste(bridge, 5071)
    try:
        convite = pareador.gerar_convite(validade_seg=300)
        token = pareador.trocar_convite(convite)
        with pytest.raises(ConviteInvalido):
            pareador.trocar_convite(convite)

        async def _usar(token_usado, troca_fechada, connection_id, hint):
            import websockets

            try:
                async with websockets.connect(
                    f"ws://127.0.0.1:5071?token={token_usado}",
                    origin="http://127.0.0.1:5071",
                ) as ws:
                    await ws.send(json.dumps({"tipo": "hello", "connection_id": connection_id,
                                              "tab_id": "aba-1", "meeting_hint": hint,
                                              "active": True, "client_wall_ms": 1_789_848_060_000,
                                              "client_monotonic_ms": 1000}))
                    await asyncio.sleep(0.2)
            except Exception:
                troca_fechada.append(True)

        asyncio.run(_usar(token, [], "c1", "abc-defg-hij"))
        time.sleep(0.2)
        assert bridge.hint_ativo_unico() == "abc-defg-hij"
        pareador.revogar_token(token)
        fechada = []
        asyncio.run(_usar(token, fechada, "c2", "xyz-abcd-efg"))
        time.sleep(0.2)
        assert bridge.hint_ativo_unico() == "abc-defg-hij"
    finally:
        bridge.parar()
        thread.join(timeout=2)


def test_convite_expirado_nao_troca():
    from meet_bridge import ConviteInvalido, Pareador

    pareador = Pareador()
    convite = pareador.gerar_convite(validade_seg=0)
    with pytest.raises(ConviteInvalido):
        pareador.trocar_convite(convite)


def test_frame_grande_rejeitado():
    pytest.importorskip("websockets")
    import asyncio
    import time

    from meet_bridge import MeetBridge

    bridge = MeetBridge(token="tk-grande")
    thread = _servidor_teste(bridge, 5072)
    try:
        async def _enviar():
            import websockets

            try:
                async with websockets.connect(
                    "ws://127.0.0.1:5072?token=tk-grande",
                    origin="http://127.0.0.1:5072",
                ) as ws:
                    await ws.send("z" * (32 * 1024))
            except Exception:
                pass

        asyncio.run(_enviar())
        time.sleep(0.3)
        assert bridge.drenar_eventos() == []
    finally:
        bridge.parar()
        thread.join(timeout=2)


def test_rajada_acima_do_limite_descartada():
    pytest.importorskip("websockets")
    import asyncio
    import time

    from meet_bridge import MeetBridge

    bridge = MeetBridge(token="tk-rajada")
    thread = _servidor_teste(bridge, 5073)
    try:
        async def _enviar():
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:5073?token=tk-rajada",
                origin="http://127.0.0.1:5073",
            ) as ws:
                for i in range(100):
                    try:
                        await ws.send(json.dumps({"nome": f"P{i}", "ts_ms": i, "tipo": "ativo"}))
                    except Exception:
                        break

        asyncio.run(_enviar())
        time.sleep(0.3)
        drenados = bridge.drenar_eventos()
        assert len(drenados) < 100
        assert bridge.contador_descarte_rajada >= 1
    finally:
        bridge.parar()
        thread.join(timeout=2)


def test_reconexao_mesma_sessao_ok():
    pytest.importorskip("websockets")
    import asyncio
    import time

    from meet_bridge import MeetBridge

    bridge = MeetBridge(token="tk-reconecta")
    thread = _servidor_teste(bridge, 5074)
    try:
        async def _enviar(nome):
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:5074?token=tk-reconecta",
                origin="http://127.0.0.1:5074",
            ) as ws:
                await ws.send(json.dumps({"nome": nome, "ts_ms": 1, "tipo": "ativo"}))

        asyncio.run(_enviar("Aba1"))
        time.sleep(0.2)
        asyncio.run(_enviar("Aba1"))
        time.sleep(0.2)
        assert len(bridge.drenar_eventos()) == 2
    finally:
        bridge.parar()
        thread.join(timeout=2)


def test_sender_outro_site_rejeitado():
    pytest.importorskip("websockets")
    import asyncio
    import time

    from meet_bridge import MeetBridge

    bridge = MeetBridge(token="tk-origin")
    thread = _servidor_teste(bridge, 5075)
    try:
        async def _enviar():
            import websockets

            try:
                async with websockets.connect(
                    "ws://127.0.0.1:5075?token=tk-origin",
                    origin="https://evil.example.test",
                ) as ws:
                    await ws.send(json.dumps({"nome": "Ana", "ts_ms": 1, "tipo": "ativo"}))
            except Exception:
                pass

        asyncio.run(_enviar())
        time.sleep(0.3)
        assert bridge.drenar_eventos() == []
    finally:
        bridge.parar()
        thread.join(timeout=2)


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
            async with websockets.connect(uri, origin=f"http://127.0.0.1:{porta}") as ws:
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
        async with websockets.connect(uri, origin=f"http://127.0.0.1:{porta}") as ws:
            await ws.send(json.dumps({"nome": "Ana", "ts_ms": 10500, "tipo": "ativo"}))

    asyncio.run(_enviar())
    time.sleep(0.3)
    eventos = bridge.drenar_eventos()
    bridge.parar()
    thread.join(timeout=2)
    assert len(eventos) == 1
    assert eventos[0]["nome"] == "Ana"
