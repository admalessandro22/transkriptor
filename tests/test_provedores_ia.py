# -*- coding: utf-8 -*-
"""T-15.D1 / FR-15.D1 — um só caminho até o Ollama, com URL configurável e só loopback."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import config_user
import provedores_ia
from provedores_ia import ErroProvedor, ProvedorOllama, normalizar_url_ollama, url_ollama
from tests.fake_ollama import FakeOllama

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def fake():
    f = FakeOllama(modelos=["granite4.1:3b", "gemma4:latest"], chat_reply="resposta fake")
    f.start()
    yield f
    f.stop()


def test_ollama_lista_modelos(fake):
    modelos = ProvedorOllama(fake.url).listar_modelos()
    assert [m.id for m in modelos] == ["granite4.1:3b", "gemma4:latest"]
    assert all(m.local for m in modelos)


def test_estado_online_com_versao(fake):
    estado = ProvedorOllama(fake.url).estado()
    assert estado.estado == "online" and estado.versao == "0.34.4-fake"


def test_offline_estado_offline():
    estado = ProvedorOllama("http://127.0.0.1:1").estado()
    assert estado.estado == "offline"
    assert ProvedorOllama("http://127.0.0.1:1").listar_modelos() == []


def test_stream_ndjson_normalizado(fake):
    pedacos = list(ProvedorOllama(fake.url).conversar_stream([{"role": "user", "content": "oi"}], modelo="m"))
    assert "".join(pedacos) == "resposta fake"


def test_conversa_sincrona_aceita_ndjson_e_passa_opcoes(fake):
    texto = ProvedorOllama(fake.url).conversar([{"role": "user", "content": "oi"}], modelo="m",
                                               opcoes={"num_ctx": 4096}, pensar=False)
    assert texto == "resposta fake"
    corpo = [r for r in fake.requests if r["path"].startswith("/api/chat")][-1]["body"]
    assert corpo["think"] is False and corpo["options"] == {"num_ctx": 4096} and corpo["stream"] is False


def test_erro_vira_erro_de_provedor_sem_conteudo():
    with pytest.raises(ErroProvedor) as erro:
        ProvedorOllama("http://127.0.0.1:1").conversar([{"role": "user", "content": "segredo"}], modelo="m")
    assert "segredo" not in str(erro.value) and erro.value.codigo == "indisponivel"


@pytest.mark.parametrize("bruto,esperado", [
    ("0.0.0.0:11434", "http://127.0.0.1:11434"),
    ("localhost:8080", "http://localhost:8080"),
    ("http://127.0.0.1", "http://127.0.0.1:11434"),
    ("127.0.0.1:11434/", "http://127.0.0.1:11434"),
])
def test_ollama_host_normalizado(bruto, esperado):
    assert normalizar_url_ollama(bruto) == esperado


@pytest.mark.parametrize("bruto", ["http://192.168.0.10:11434", "https://exemplo.com", "ollama.local:11434"])
def test_url_nao_loopback_recusada(bruto):
    with pytest.raises(ValueError):
        normalizar_url_ollama(bruto)


def test_prioridade_da_url(monkeypatch):
    monkeypatch.setattr("config.OLLAMA_URL", "http://127.0.0.1:1111")
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert url_ollama() == "http://127.0.0.1:1111"
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:2222")
    assert url_ollama() == "http://127.0.0.1:2222"
    config_user.atualizar(ollama_url="http://localhost:3333")
    assert url_ollama() == "http://localhost:3333"
    config_user.atualizar(ollama_url="http://10.0.0.5:11434")  # fora do loopback: ignorada
    assert url_ollama() == "http://127.0.0.1:2222"


def test_contexto_do_modelo(fake):
    assert ProvedorOllama(fake.url).contexto("m") == 8192


def test_nenhum_modulo_fala_com_o_ollama_direto():
    """Só provedores_ia.py monta URL do Ollama; o resto usa a camada."""
    ignorados = {"provedores_ia.py", "config.py"}
    ofensores = []
    for arquivo in RAIZ.glob("*.py"):
        if arquivo.name in ignorados:
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "OLLAMA_URL" in texto or "/api/tags" in texto or '"/api/show"' in texto:
            ofensores.append(arquivo.name)
    assert ofensores == []
