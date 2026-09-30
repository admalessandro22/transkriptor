# -*- coding: utf-8 -*-
"""T-15.E3 / FR-15.E3 — assistente de primeiro uso: Ollama, modelo, extensão."""
from __future__ import annotations

import time

import pytest

import config_user
from tests.fake_ollama import FakeOllama


@pytest.fixture
def cliente(monkeypatch):
    from assistente import app

    monkeypatch.setattr("central_ia._hardware", lambda: (False, 0.0))
    monkeypatch.setattr("central_primeiro_uso._ram_gb", lambda: 8.0)
    return app.test_client()


@pytest.fixture
def fake(monkeypatch):
    f = FakeOllama(modelos=["granite4.1:3b"])
    f.start()
    monkeypatch.setattr("config.OLLAMA_URL", f.url)
    yield f
    f.stop()


def test_estado_inclui_deteccao_sem_caminho_pessoal(cliente, headers_token, fake):
    dados = cliente.get("/api/primeiro-uso", headers=headers_token).get_json()
    assert dados["ollama"]["estado"] == "online"
    assert [m["id"] for m in dados["ollama"]["modelos"]] == ["granite4.1:3b"]
    assert dados["whisper_recomendado"] == "small"
    assert dados["modelo_sugerido"]["id"] == "granite4.1:3b"
    assert dados["concluido"] is False
    assert "executavel" not in dados["ollama"] and "Users" not in str(dados)


def test_ollama_ausente(cliente, headers_token, monkeypatch):
    monkeypatch.setattr("config.OLLAMA_URL", "http://127.0.0.1:1")
    monkeypatch.setattr("central_primeiro_uso._detectar",
                        lambda: __import__("detector_ollama").detectar_ollama(
                            which=lambda n: None, existe=lambda p: False, instalacoes_registro=lambda: []))
    dados = cliente.get("/api/primeiro-uso", headers=headers_token).get_json()
    assert dados["ollama"]["estado"] == "nao_instalado"
    assert dados["ollama"]["pagina_instalacao"] == "https://ollama.com/download"


@pytest.mark.parametrize("ram,cuda,vram,esperado", [
    (8.0, False, 0.0, "granite4.1:3b"), (32.0, False, 0.0, "gemma4:latest"), (16.0, True, 8.0, "gemma4:latest"),
    (16.0, True, 4.0, "granite4.1:3b"),
])
def test_modelo_sugerido_pelo_hardware(ram, cuda, vram, esperado):
    from central_primeiro_uso import modelo_sugerido

    assert modelo_sugerido(ram_gb=ram, cuda=cuda, vram_gb=vram)["id"] == esperado


def test_baixar_modelo_progresso(cliente, headers_token, fake):
    r = cliente.post("/api/primeiro-uso/ollama/baixar", json={"modelo": "gemma4:latest"}, headers=headers_token)
    assert r.status_code == 202
    id_ = r.get_json()["id"]
    for _ in range(50):
        progresso = cliente.get(f"/api/primeiro-uso/ollama/baixar/{id_}", headers=headers_token).get_json()
        if progresso["estado"] != "baixando":
            break
        time.sleep(0.1)
    assert progresso["estado"] == "concluido" and progresso["percentual"] == 100
    assert "gemma4:latest" in fake.modelos


@pytest.mark.parametrize("modelo", ["", "a b", "x" * 81, "../../etc", "gemma4;rm"])
def test_baixar_recusa_nome_invalido(cliente, headers_token, modelo):
    r = cliente.post("/api/primeiro-uso/ollama/baixar", json={"modelo": modelo}, headers=headers_token)
    assert r.status_code == 400


def test_iniciar_ollama_exige_confirmacao(cliente, headers_token, monkeypatch):
    lancados = []
    monkeypatch.setattr("central_primeiro_uso._lancar", lambda exe: lancados.append(exe))
    monkeypatch.setattr("central_primeiro_uso._detectar", lambda: type("D", (), {
        "estado": "parado", "executavel": r"C:\Apps\Ollama\ollama.exe", "versao": None, "url": "u", "modelos": []})())
    assert cliente.post("/api/primeiro-uso/ollama/iniciar", json={}, headers=headers_token).status_code == 409
    r = cliente.post("/api/primeiro-uso/ollama/iniciar", json={"confirmado": True}, headers=headers_token)
    assert r.status_code == 202 and lancados == [r"C:\Apps\Ollama\ollama.exe"]


def test_concluido_nao_reabre(cliente, headers_token):
    from transkriptor_menu_flows import abrir_primeiro_uso_se_preciso

    abertos = []
    assert abrir_primeiro_uso_se_preciso(object(), abrir=lambda app, pagina: abertos.append(pagina)) is True
    assert abertos == ["primeiro-uso"]
    assert cliente.post("/api/primeiro-uso/concluir", json={}, headers=headers_token).status_code == 200
    assert config_user.carregar()["assistente_inicial_concluido"] is True
    assert abrir_primeiro_uso_se_preciso(object(), abrir=lambda app, pagina: abertos.append(pagina)) is False


def test_pagina_existe(cliente, headers_token):
    r = cliente.get("/primeiro-uso", headers=headers_token)
    assert r.status_code == 200 and b"Primeiros passos" in r.data
