# -*- coding: utf-8 -*-
"""Testes de token de sessão e truncagem (Fase 5 — SEC-4, FR-5.3)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from assistente import HEADER_TOKEN, app, obter_token_sessao


@pytest.fixture
def headers_token():
    return {HEADER_TOKEN: obter_token_sessao()}


def test_api_sem_token_retorna_403():
    client = app.test_client()
    resp = client.get("/api/transcricoes")
    assert resp.status_code == 403
    assert resp.get_json()["erro"] == "Token inválido"


def test_api_com_token_invalido_retorna_403():
    client = app.test_client()
    resp = client.get("/api/transcricoes", headers={HEADER_TOKEN: "token-errado"})
    assert resp.status_code == 403
    assert resp.get_json()["erro"] == "Token inválido"


def test_api_com_token_query_param_retorna_403(tmp_transcricoes, monkeypatch):
    """SEC-4.1: token em query em /api/* é rejeitado."""
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_transcricoes))
    client = app.test_client()
    token = obter_token_sessao()
    resp = client.get(f"/api/transcricoes?token={token}")
    assert resp.status_code == 403


def test_api_com_cookie_valido_retorna_200(tmp_transcricoes, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_transcricoes))
    client = app.test_client()
    client.set_cookie("tkpt_token", obter_token_sessao())
    resp = client.get("/api/transcricoes")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_index_token_seta_cookie_e_redirect():
    client = app.test_client()
    token = obter_token_sessao()
    resp = client.get(f"/?token={token}", follow_redirects=False)
    assert resp.status_code in (302, 301)
    cookies = resp.headers.getlist("Set-Cookie")
    assert any("tkpt_token=" in c and "HttpOnly" in c for c in cookies)


def test_chat_corpo_grande_413(tmp_path, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "ok.txt").write_text("x", encoding="utf-8")
    client = app.test_client()
    corpo = {"modelo": "m", "transcricao": "ok.txt", "pergunta": "q", "pad": "x" * (300 * 1024)}
    resp = client.post("/api/chat", json=corpo, headers=headers_token)
    assert resp.status_code == 413


def test_chat_historico_longo_400(tmp_path, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "ok.txt").write_text("x", encoding="utf-8")
    client = app.test_client()
    hist = [{"role": "user", "content": "x"} for _ in range(50)]
    resp = client.post(
        "/api/chat",
        json={"modelo": "m", "transcricao": "ok.txt", "pergunta": "q", "historico": hist},
        headers=headers_token,
    )
    assert resp.status_code == 400


def test_api_saude_ollama_off(monkeypatch, headers_token):
    monkeypatch.setattr("assistente.OLLAMA_URL", "http://127.0.0.1:1")
    client = app.test_client()
    resp = client.get("/api/saude", headers=headers_token)
    assert resp.status_code == 200
    dados = resp.get_json()
    assert dados["ollama"] is False
    assert "versao" in dados


def test_api_com_token_valido_retorna_200(tmp_transcricoes, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_transcricoes))
    client = app.test_client()
    resp = client.get("/api/transcricoes", headers=headers_token)
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_get_index_sem_token_permanece_200():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Transkriptor" in resp.get_data(as_text=True)


def test_api_chat_sem_token_retorna_403(tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "ok.txt").write_text("conteudo", encoding="utf-8")
    client = app.test_client()
    resp = client.post(
        "/api/chat",
        json={"modelo": "m", "transcricao": "ok.txt", "pergunta": "q"},
    )
    assert resp.status_code == 403
    assert resp.get_json()["erro"] == "Token inválido"


def test_api_chat_com_token_nao_403_por_token(tmp_path, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    arquivo = tmp_path / "ok.txt"
    arquivo.write_text("x" * 50, encoding="utf-8")
    client = app.test_client()

    def _stream(*_a, **_k):
        yield b'{"message":{"content":"ok"},"done":false}\n'
        yield b'{"message":{"content":""},"done":true}\n'

    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.__iter__ = MagicMock(return_value=iter(_stream()))

    with patch("assistente.urllib.request.urlopen", return_value=mock_resp):
        resp = client.post(
            "/api/chat",
            json={"modelo": "m", "transcricao": "ok.txt", "pergunta": "q"},
            headers=headers_token,
        )
    assert resp.status_code != 403 or resp.get_json().get("erro") != "Token inválido"


def test_transcricao_grande_indica_truncada_ou_map_reduce(tmp_path, monkeypatch, headers_token):
    """FR-4.3: transcrição grande usa map-reduce (prefixo) e header Truncada."""
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    monkeypatch.setattr("assistente.MAX_CHARS_TRANSCRICAO", 1000)
    monkeypatch.setattr("assistente.consultar_context_length", lambda _m: None)
    (tmp_path / "grande.txt").write_text("A" * 5000, encoding="utf-8")
    client = app.test_client()

    with patch("assistente._chamar_ollama_sync", return_value="resumo ok"):
        resp = client.post(
            "/api/chat",
            json={"modelo": "m", "transcricao": "grande.txt", "pergunta": "q"},
            headers=headers_token,
        )
        body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert resp.headers.get("X-Transkriptor-Truncada") == "true"
    assert "reunião longa" in body.lower() or "truncad" in body.lower()


def test_html_inclui_token_em_fetch():
    from assistente import HTML

    assert "X-Transkriptor-Token" in HTML
    assert "token" in HTML.lower()