# -*- coding: utf-8 -*-
"""T-15.E2 / FR-15.E2 — pareamento automático pelo host de Native Messaging.

Nada aqui escreve no registro real: a escrita é injetada.
"""
from __future__ import annotations

import io
import json
import struct

import pytest

import config
import ponte_nativa
from ponte_nativa import AppDesligado, atender, escrever_mensagem, ler_mensagem

ORIGEM = f"chrome-extension://{config.EXTENSAO_IDS_PERMITIDOS[0]}/"
PEDIDO = {"cmd": "obter_codigo_pareamento", "v": 1}


def test_comando_unico():
    resposta = atender(PEDIDO, ORIGEM, obter_codigo=lambda: ("pair-abc", 5051))
    assert resposta == {"ok": True, "codigo": "pair-abc", "porta": 5051}


@pytest.mark.parametrize("pedido", [{"cmd": "executar", "v": 1}, {"cmd": "obter_codigo_pareamento", "v": 2},
                                    "texto", None, {"cmd": "obter_codigo_pareamento", "v": 1, "arg": "x"}])
def test_outro_comando_recusado(pedido):
    chamado = []
    resposta = atender(pedido, ORIGEM, obter_codigo=lambda: chamado.append(1) or ("pair-x", 1))
    assert resposta == {"ok": False, "erro": "comando_invalido"} and chamado == []


@pytest.mark.parametrize("origem", [None, "chrome-extension://abcdefghijklmnopabcdefghijklmnop/", "https://evil.test/"])
def test_origem_nao_permitida_recusada(origem):
    assert atender(PEDIDO, origem, obter_codigo=lambda: ("pair-x", 1)) == {"ok": False, "erro": "recusado"}


def test_app_desligado_erro():
    def desligado():
        raise AppDesligado()

    assert atender(PEDIDO, ORIGEM, obter_codigo=desligado) == {"ok": False, "erro": "app_nao_iniciado"}


def test_protocolo_stdio_ida_e_volta():
    corpo = json.dumps(PEDIDO).encode()
    entrada = io.BytesIO(struct.pack("<I", len(corpo)) + corpo)
    assert ler_mensagem(entrada) == PEDIDO
    saida = io.BytesIO()
    escrever_mensagem(saida, {"ok": True})
    bruto = saida.getvalue()
    assert struct.unpack("<I", bruto[:4])[0] == len(bruto) - 4 and json.loads(bruto[4:]) == {"ok": True}


def test_mensagem_grande_demais_recusada():
    assert ler_mensagem(io.BytesIO(struct.pack("<I", 10_000_000) + b"{}")) is None


def test_registro_hkcu_chrome_edge(tmp_path):
    from instalador.registrar_host import CHAVES, registrar

    escritas = {}
    manifesto = registrar(tmp_path / "app", python="C:/Py/python.exe", destino=tmp_path / "native",
                          escrever=lambda chave, valor: escritas.__setitem__(chave, valor))
    dados = json.loads(manifesto.read_text(encoding="utf-8"))
    assert dados["name"] == "com.transkriptor.ponte" and dados["type"] == "stdio"
    assert dados["allowed_origins"] == [f"chrome-extension://{i}/" for i in config.EXTENSAO_IDS_PERMITIDOS]
    lancador = tmp_path / "native" / "transkriptor-ponte.bat"
    assert dados["path"] == str(lancador) and "ponte_nativa.py" in lancador.read_text(encoding="utf-8")
    assert set(escritas) == set(CHAVES) and all(v == str(manifesto) for v in escritas.values())
    assert any("Google\\Chrome" in c for c in CHAVES) and any("Microsoft\\Edge" in c for c in CHAVES)


def test_codigo_vem_da_ponte_e_autentica(chave_teste, tmp_path, monkeypatch):
    """Ponta a ponta: segredo publicado → host pede → código de uso único que a ponte aceita."""
    from meet_bridge import MeetBridge, iniciar_bridge_em_thread
    from meet_pareamento import Pareador

    monkeypatch.setattr(config, "ARQUIVO_SEGREDO_PONTE", str(tmp_path / "ponte.segredo"))
    pareador = Pareador(arquivo=tmp_path / "pareamento.json")
    bridge = MeetBridge(pareador=pareador)
    thread = iniciar_bridge_em_thread(bridge, "127.0.0.1", 5086)
    try:
        segredo = json.loads((tmp_path / "ponte.segredo").read_text(encoding="utf-8"))
        assert segredo["porta"] == 5086 and len(segredo["segredo"]) >= 32
        codigo, porta = ponte_nativa.obter_codigo_do_app()
        assert codigo.startswith("pair-") and porta == 5086
        token, era_convite = pareador.autenticar(codigo)
        assert era_convite and token.startswith("sess-")
    finally:
        bridge.parar()
        thread.join(timeout=2)


def test_segredo_errado_nao_ganha_codigo(chave_teste, tmp_path, monkeypatch):
    from meet_bridge import MeetBridge, iniciar_bridge_em_thread
    from meet_pareamento import Pareador

    monkeypatch.setattr(config, "ARQUIVO_SEGREDO_PONTE", str(tmp_path / "ponte.segredo"))
    bridge = MeetBridge(pareador=Pareador(arquivo=tmp_path / "pareamento.json"))
    thread = iniciar_bridge_em_thread(bridge, "127.0.0.1", 5087)
    try:
        (tmp_path / "ponte.segredo").read_text(encoding="utf-8")
        (tmp_path / "ponte.segredo").write_text(json.dumps({"porta": 5087, "segredo": "x" * 43}), encoding="utf-8")
        with pytest.raises(AppDesligado):
            ponte_nativa.obter_codigo_do_app()
    finally:
        bridge.parar()
        thread.join(timeout=2)


def test_sem_arquivo_de_segredo_app_desligado(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARQUIVO_SEGREDO_PONTE", str(tmp_path / "nao-existe"))
    with pytest.raises(AppDesligado):
        ponte_nativa.obter_codigo_do_app()
