# -*- coding: utf-8 -*-
"""UX-14.C3 — ações da Central: aprender voz separado da correção por reunião."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from assistente import HEADER_TOKEN, app, obter_token_sessao


@pytest.fixture()
def cliente():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def sem_provedor():
    import central_api

    central_api.registrar_provedor_centroides(None)
    yield
    central_api.registrar_provedor_centroides(None)


@pytest.fixture()
def com_centroides():
    import central_api

    centroides = {"FALANTE_00": np.ones(192, dtype=np.float32), "FALANTE_01": np.zeros(192, dtype=np.float32)}
    central_api.registrar_provedor_centroides(lambda: centroides)
    yield centroides
    central_api.registrar_provedor_centroides(None)


def _headers():
    return {HEADER_TOKEN: obter_token_sessao()}


def test_aprender_voz_sem_centroides_404(cliente, sem_provedor):
    resposta = cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_00", "nome": "Ana"}, headers=_headers())
    assert resposta.status_code == 404
    assert "separação de vozes" in resposta.get_json()["erro"]


def test_aprender_voz_exige_header_secreto(cliente, com_centroides):
    from assistente import COOKIE_TOKEN

    cliente.set_cookie(COOKIE_TOKEN, obter_token_sessao())
    resposta = cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_00", "nome": "Ana"})
    assert resposta.status_code == 403


def test_aprender_voz_valida_entrada(cliente, com_centroides):
    assert cliente.post("/api/acoes/aprender-voz", json={"rotulo": "x", "nome": "Ana"}, headers=_headers()).status_code == 400
    assert cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_00", "nome": "A"}, headers=_headers()).status_code == 400
    assert cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_07", "nome": "Ana"}, headers=_headers()).status_code == 404


def test_aprender_voz_persiste_no_arquivo_de_vozes(cliente, com_centroides, monkeypatch, tmp_path, chave_teste):
    import central_api

    destino = tmp_path / "vozes_conhecidas.json"
    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(destino))
    resposta = cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_00", "nome": "Ana Souza"}, headers=_headers())
    assert resposta.status_code == 200, resposta.get_json()
    assert resposta.get_json()["salvo"] == "Ana Souza"
    assert destino.exists() or (tmp_path / "vozes_conhecidas.enc").exists()


def test_aprender_voz_sem_chave_falha_fechado(cliente, com_centroides, monkeypatch, tmp_path):
    """SEC-13.E1: sem cifra disponível, a biometria não é gravada e a falha é explícita."""
    import central_api

    from politica_privacidade import ProtectionMode

    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(tmp_path / "vozes_conhecidas.json"))
    monkeypatch.setattr("identificador_voz._usar_criptografia_voz", lambda: False)
    monkeypatch.setattr("politica_privacidade.modo_efetivo", lambda: ProtectionMode.PROTECTED)
    resposta = cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_00", "nome": "Ana Souza"}, headers=_headers())
    assert resposta.status_code == 503
    assert "Proteção indisponível" in resposta.get_json()["erro"]
    assert not (tmp_path / "vozes_conhecidas.json").exists()


def test_corrigir_nome_nao_cadastra_biometria(cliente, monkeypatch, tmp_path):
    """DU-07: a correção por reunião nunca toca o arquivo de vozes conhecidas."""
    from resultado_edicao import VERSAO_SEGMENTOS

    pasta = tmp_path / "transcricoes"
    (pasta / "resultados").mkdir(parents=True)
    (pasta / "resultados" / "reuniao-x.json").write_text(json.dumps({
        "schema_version": VERSAO_SEGMENTOS, "revision": "rev-1", "mapeamento": {}, "historico": [],
        "segmentos": [{"segment_id": "s1", "start_ms": 0, "end_ms": 1000, "audio_source": "loopback", "text": "oi", "speaker_cluster_id": "FALANTE_00"}],
    }), encoding="utf-8")
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(pasta))

    def _proibido(*_a, **_k):
        raise AssertionError("correção por reunião cadastrou biometria")

    monkeypatch.setattr("identificador_voz.renomear_falante", _proibido)
    monkeypatch.setattr("renomear_falante_flow.renomear_falante", _proibido)
    resposta = cliente.post("/api/reunioes/reuniao-x/correcao", json={"expected_revision": "rev-1", "speaker_cluster_id": "FALANTE_00", "display_name": "Ana"}, headers=_headers())
    assert resposta.status_code == 200, resposta.get_json()
    assert resposta.get_json()["revision"] == "rev-2"


def test_index_com_next_redireciona_para_pagina_da_central(cliente):
    resposta = cliente.get(f"/?token={obter_token_sessao()}&next=participantes")
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/participantes")
    assert any(c.startswith("tkpt_token=") for c in resposta.headers.getlist("Set-Cookie"))
    fora = cliente.get(f"/?token={obter_token_sessao()}&next=../etc")
    assert fora.status_code == 302 and fora.headers["Location"].endswith("/")


def test_dialogos_tk_de_nome_removidos():
    fonte = Path(__file__).resolve().parent.parent
    flows = (fonte / "transkriptor_menu_flows.py").read_text(encoding="utf-8")
    fluxo = (fonte / "renomear_falante_flow.py").read_text(encoding="utf-8")
    assert "_renomear_dialog" not in flows and "iniciar_renomear_falante_ui" not in flows
    assert "corrigir_nome_reuniao_ui" not in flows and "corrigir_nome_reuniao_ui" not in fluxo
    assert "simpledialog" not in fluxo
    assert "def abrir_central(" in flows
