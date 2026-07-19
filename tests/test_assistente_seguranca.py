# -*- coding: utf-8 -*-
"""Testes de segurança do assistente (Fase 1 — SEC-1, FR-1.3/1.4)."""
import pytest

from assistente import app, caminho_transcricao_seguro
from tests.front_assistente import HTML


def test_rejeita_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    assert caminho_transcricao_seguro("../../etc/passwd") is None
    assert caminho_transcricao_seguro("..\\..\\windows\\win.ini") is None
    assert caminho_transcricao_seguro("../../windows/system.ini") is None


def test_aceita_arquivo_valido(tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "ok.txt").write_text("x", encoding="utf-8")
    result = caminho_transcricao_seguro("ok.txt")
    assert result is not None
    assert result.endswith("ok.txt")


def test_rejeita_arquivo_inexistente(tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    assert caminho_transcricao_seguro("nao_existe.txt") is None


def test_api_chat_rejeita_path_traversal(tmp_path, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    client = app.test_client()
    resp = client.post(
        "/api/chat",
        json={
            "modelo": "test",
            "transcricao": "../../config.py",
            "pergunta": "teste",
        },
        headers=headers_token,
    )
    assert resp.status_code == 403
    assert resp.get_json() == {"erro": "Acesso negado"}


def test_html_usa_build_select_options_sem_innerhtml_dados():
    assert "function buildSelectOptions" in HTML
    inicio = HTML.find("async function loadList")
    assert inicio != -1
    bloco = HTML[inicio : inicio + 1200]
    assert "buildSelectOptions" in bloco
    assert "selTrans.innerHTML = d.map" not in bloco


def test_html_modelos_usa_build_model_options_sem_innerhtml():
    assert "function buildModelOptions" in HTML
    inicio = HTML.find("async function loadList")
    bloco = HTML[inicio : inicio + 1500]
    assert "buildModelOptions" in bloco
    assert "selMod.innerHTML = d.map" not in bloco