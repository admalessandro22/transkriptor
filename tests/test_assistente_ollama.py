# -*- coding: utf-8 -*-
"""T-F4 — Ollama confiável (num_ctx, map-reduce, fake server)."""
import pytest

from assistente import HEADER_TOKEN, app, api_modelos, orcamento_chars, obter_token_sessao
from resumo_longo import dividir_em_blocos, responder_longo
from tests.fake_ollama import FakeOllama


@pytest.fixture
def fake_ollama(monkeypatch):
    fake = FakeOllama(modelos=["m1", "m2"], context_length=4096, chat_reply="ok")
    url = fake.start()
    monkeypatch.setattr("assistente.OLLAMA_URL", url)
    monkeypatch.setattr("config.OLLAMA_URL", url)
    yield fake
    fake.stop()


def test_fake_ollama_api_modelos(fake_ollama, monkeypatch):
    monkeypatch.setattr("assistente.OLLAMA_URL", fake_ollama.url)
    with app.test_request_context():
        # api_modelos uses OLLAMA_URL from module
        from assistente import api_modelos as fn

        # call via client is cleaner
    client = app.test_client()
    r = client.get("/api/modelos", headers={HEADER_TOKEN: obter_token_sessao()})
    assert r.status_code == 200
    assert r.get_json() == ["m1", "m2"]


def test_orcamento_chars():
    o4k = orcamento_chars(4096)
    o32k = orcamento_chars(32768)
    assert o4k < o32k
    assert o4k > 1000


def test_api_chat_envia_num_ctx(fake_ollama, tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    monkeypatch.setattr("assistente._cache_ctx", {})
    (tmp_path / "r.txt").write_text("ola reuniao curta", encoding="utf-8")
    client = app.test_client()
    r = client.post(
        "/api/chat",
        headers={HEADER_TOKEN: obter_token_sessao()},
        json={"modelo": "m1", "transcricao": "r.txt", "pergunta": "resumo?"},
    )
    assert r.status_code == 200
    # consome stream
    _ = r.get_data(as_text=True)
    posts = [x for x in fake_ollama.requests if x["method"] == "POST" and "chat" in x["path"]]
    assert posts
    assert posts[-1]["body"].get("options", {}).get("num_ctx") == 4096


def test_map_reduce_3_blocos():
    chamadas = []

    def chamar(modelo, msgs):
        chamadas.append(msgs)
        return f"resumo-{len(chamadas)}"

    blocos = ["a" * 10, "b" * 10, "c" * 10]
    out = responder_longo("m", blocos, "o que foi?", chamar)
    assert len(chamadas) == 4  # 3 resumos + 1 final
    assert "resumo" in out


def test_dividir_preserva_linhas():
    texto = "linha1\nlinha2\nlinha3\n"
    blocos = dividir_em_blocos(texto, 20)
    assert "".join(blocos) == texto


def test_chat_longo_prefixo(fake_ollama, tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    monkeypatch.setattr("assistente._cache_ctx", {"m1": 512})
    # orçamento pequeno
    monkeypatch.setattr("assistente.orcamento_chars", lambda ctx: 50)
    (tmp_path / "longa.txt").write_text("palavra " * 200, encoding="utf-8")
    client = app.test_client()
    r = client.post(
        "/api/chat",
        headers={HEADER_TOKEN: obter_token_sessao()},
        json={"modelo": "m1", "transcricao": "longa.txt", "pergunta": "resumo"},
    )
    body = r.get_data(as_text=True)
    assert "Reunião longa" in body or "reuniao longa" in body.lower()
