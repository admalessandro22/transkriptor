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


def test_api_com_token_query_param_retorna_200(tmp_transcricoes, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_transcricoes))
    client = app.test_client()
    token = obter_token_sessao()
    resp = client.get(f"/api/transcricoes?token={token}")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


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


def test_transcricao_grande_indica_truncada(tmp_path, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    monkeypatch.setattr("assistente.MAX_CHARS_TRANSCRICAO", 1000)
    (tmp_path / "grande.txt").write_text("A" * 5000, encoding="utf-8")
    client = app.test_client()

    def _stream(*_a, **_k):
        yield b'{"message":{"content":"r"},"done":true}\n'

    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.__iter__ = MagicMock(return_value=iter(_stream()))

    with patch("assistente.urllib.request.urlopen", return_value=mock_resp) as mock_open:
        resp = client.post(
            "/api/chat",
            json={"modelo": "m", "transcricao": "grande.txt", "pergunta": "q"},
            headers=headers_token,
        )
        body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert resp.headers.get("X-Transkriptor-Truncada") == "true"
    assert "truncad" in body.lower()
    assert mock_open.called
    sent = mock_open.call_args[0][0]
    payload = json.loads(sent.data.decode("utf-8"))
    system = payload["messages"][0]["content"]
    assert len(system) < 5000 + 500


def test_html_inclui_token_em_fetch():
    from assistente import HTML

    assert "X-Transkriptor-Token" in HTML
    assert "token" in HTML.lower()