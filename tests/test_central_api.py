# -*- coding: utf-8 -*-
"""UX-14.C3 — ações da Central: aprender voz separado da correção por reunião."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from assistente import HEADER_TOKEN, app, obter_token_sessao


@pytest.fixture()
def cliente():
    app.config["TESTING"] = True
    return app.test_client()


def _headers():
    return {HEADER_TOKEN: obter_token_sessao()}


def test_aprender_voz_exige_reuniao_e_revisao(cliente):
    resposta = cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_00", "nome": "Ana"}, headers=_headers())
    assert resposta.status_code == 400
    assert "Reunião" in resposta.get_json()["erro"]


def test_aprender_voz_exige_header_secreto(cliente):
    from assistente import COOKIE_TOKEN

    cliente.set_cookie(COOKIE_TOKEN, obter_token_sessao())
    resposta = cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_00", "nome": "Ana"})
    assert resposta.status_code == 403


def test_aprender_voz_valida_entrada(cliente):
    assert cliente.post("/api/acoes/aprender-voz", json={"rotulo": "x", "nome": "Ana"}, headers=_headers()).status_code == 400
    assert cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_00", "nome": "A"}, headers=_headers()).status_code == 400
    assert cliente.post("/api/acoes/aprender-voz", json={"rotulo": "FALANTE_07", "nome": "Ana"}, headers=_headers()).status_code == 400


def test_aprender_voz_espera_gravacao_ou_processamento(cliente, monkeypatch):
    import aprendizado_voz_reuniao
    import central_resumos

    monkeypatch.setattr(central_resumos, "_app_ocupado", lambda: True)
    monkeypatch.setattr(
        aprendizado_voz_reuniao, "embedding_da_reuniao",
        lambda *_a, **_k: pytest.fail("não deve carregar áudio durante gravação"),
    )
    resposta = cliente.post(
        "/api/acoes/aprender-voz",
        json={"meeting_id": "a" * 32, "expected_revision": "rev-1",
              "rotulo": "FALANTE_00", "nome": "Ana"},
        headers=_headers(),
    )

    assert resposta.status_code == 409
    assert "terminar" in resposta.get_json()["erro"]


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
