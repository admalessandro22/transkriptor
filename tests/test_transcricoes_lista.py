# -*- coding: utf-8 -*-
"""UX-14.B2 — lista de reuniões sem conteúdo por padrão (T-14.B2)."""
from __future__ import annotations

import time

import pytest

from assistente import app


@pytest.fixture()
def cliente(tmp_transcricoes, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_transcricoes))
    app.config["TESTING"] = True
    return app.test_client()


def test_transcricoes_sem_preview_por_padrao(cliente, headers_token, monkeypatch):
    def _nao_ler(*_a, **_k):
        raise AssertionError("a listagem padrão não pode abrir o conteúdo")

    monkeypatch.setattr("assistente.ler_conteudo_transcricao", _nao_ler)
    dados = cliente.get("/api/transcricoes", headers=headers_token).get_json()
    assert dados and all("preview" not in d for d in dados)
    assert all(d["com_sua_voz"] is None for d in dados)
    assert {"arquivo", "data", "tipo", "tamanho_kb", "protegida"} <= set(dados[0])


def test_transcricoes_detalhes_de_um_arquivo(cliente, headers_token, tmp_transcricoes):
    com_voce = tmp_transcricoes / "reuniao_diarizado.txt"
    com_voce.write_text("[VOCÊ 00:01-00:03] eu falo\n", encoding="utf-8")
    dados = cliente.get(f"/api/transcricoes?detalhes=1&arquivo={com_voce.name}", headers=headers_token).get_json()
    assert [d["arquivo"] for d in dados] == [com_voce.name]
    assert dados[0]["com_sua_voz"] is True
    assert "eu falo" in dados[0]["preview"]


def test_transcricoes_detalhes_arquivo_invalido_e_vazio(cliente, headers_token):
    assert cliente.get("/api/transcricoes?detalhes=1&arquivo=../x.txt", headers=headers_token).get_json() == []
    assert cliente.get("/api/transcricoes?detalhes=1&arquivo=nao-existe.txt", headers=headers_token).get_json() == []


def test_mil_transcricoes_listadas_sem_ler_conteudo(cliente, headers_token, tmp_transcricoes, monkeypatch):
    for i in range(1000):
        (tmp_transcricoes / f"r{i:04d}_diarizado.txt").write_text("[VOCÊ 00:00-00:01] x\n", encoding="utf-8")

    def _nao_ler(*_a, **_k):
        raise AssertionError("listagem abriu conteúdo")

    monkeypatch.setattr("assistente.ler_conteudo_transcricao", _nao_ler)
    inicio = time.perf_counter()
    dados = cliente.get("/api/transcricoes", headers=headers_token).get_json()
    duracao = time.perf_counter() - inicio
    assert len(dados) >= 1000
    assert duracao < 1.0, f"listagem levou {duracao:.2f}s"
