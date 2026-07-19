# -*- coding: utf-8 -*-
"""Testes API e UX do assistente (Fase 4 — FR-4.*, UX-2.*)."""
import pytest

from assistente import HTML, app

CAMPOS_API = ("arquivo", "data", "tipo", "tamanho_kb", "preview", "com_sua_voz")


def test_api_transcricoes_retorna_campos_obrigatorios(tmp_transcricoes, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_transcricoes))
    client = app.test_client()
    resp = client.get("/api/transcricoes", headers=headers_token)
    assert resp.status_code == 200
    dados = resp.get_json()
    assert len(dados) == 1
    item = dados[0]
    for campo in CAMPOS_API:
        assert campo in item, f"campo ausente: {campo}"
    assert item["arquivo"].endswith(".txt")
    assert item["tipo"] in ("transcricao", "diarizado")
    assert isinstance(item["tamanho_kb"], (int, float))
    assert item["tamanho_kb"] > 0
    assert "Ola equipe" in item["preview"]


def test_api_transcricoes_tipo_diarizado(tmp_transcricoes, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_transcricoes))
    diarizado = tmp_transcricoes / "reuniao_diarizado.txt"
    diarizado.write_text("FALANTE_01: ola\n", encoding="utf-8")
    client = app.test_client()
    dados = client.get("/api/transcricoes", headers=headers_token).get_json()
    tipos = {d["arquivo"]: d["tipo"] for d in dados}
    assert tipos[diarizado.name] == "diarizado"


def test_html_timer_mensagem_15s():
    assert "O modelo está pensando" in HTML
    inicio = HTML.find("function iniciarTimer")
    assert inicio != -1
    bloco = HTML[inicio : inicio + 600]
    assert "15" in bloco
    assert "O modelo está pensando" in bloco


def test_html_progress_bar_durante_busy():
    assert "progress-bar" in HTML
    assert "progressBar" in HTML or "progress-bar" in HTML
    inicio = HTML.find("function mostrarBotoes")
    assert inicio != -1
    bloco = HTML[inicio : inicio + 400]
    assert "progress" in bloco.lower()


def test_html_drawer_mobile_375px():
    assert "☰" in HTML or "&#9776;" in HTML
    assert "375px" in HTML
    assert "drawer" in HTML.lower() or "menu-toggle" in HTML


def test_html_navegacao_teclado_action_cards():
    assert "ArrowDown" in HTML
    assert "ArrowUp" in HTML
    inicio = HTML.find("function navegarActionCards")
    assert inicio != -1
    bloco = HTML[inicio : inicio + 600]
    assert "action-card" in bloco
    assert "TEXTAREA" in bloco
    assert "idx === -1" in bloco
    assert "cards[0].focus" not in bloco


def test_html_copiar_resposta_e_tamanho_kb():
    assert "copiar" in HTML.lower()
    assert "tamanho_kb" in HTML or "tamanho-kb" in HTML or "tamanhoKb" in HTML
    inicio = HTML.find("function buildSelectOptions")
    bloco = HTML[inicio : inicio + 800]
    assert "tamanho" in bloco.lower()