# -*- coding: utf-8 -*-
"""Badge 'com sua voz' no assistente (Fase 7 — FR-7.11)."""
import pytest

from assistente import HTML, app, transcricao_contem_voce


def test_transcricao_contem_voce_detecta_rotulo():
    texto = "[VOCÊ 00:05-00:08] Obrigado por participar.\n"
    assert transcricao_contem_voce(texto) is True


def test_transcricao_contem_voce_sem_voce():
    assert transcricao_contem_voce("[FALANTE_01 00:00-00:05] ola") is False
    assert transcricao_contem_voce("transcricao simples sem diarizacao") is False


def test_api_transcricoes_com_sua_voz(tmp_transcricoes, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_transcricoes))
    com_voce = tmp_transcricoes / "reuniao_diarizado.txt"
    com_voce.write_text(
        "[VOCÊ 00:01-00:03] eu falo\n[FALANTE_01 00:04-00:06] outro\n",
        encoding="utf-8",
    )
    sem_voce = tmp_transcricoes / "outra_diarizado.txt"
    sem_voce.write_text("[FALANTE_01 00:00-00:02] so outros\n", encoding="utf-8")
    client = app.test_client()
    dados = client.get("/api/transcricoes", headers=headers_token).get_json()
    por_arquivo = {d["arquivo"]: d for d in dados}
    assert por_arquivo[com_voce.name]["com_sua_voz"] is True
    assert por_arquivo[sem_voce.name]["com_sua_voz"] is False
    assert por_arquivo["transcricao_2026-07-08_10h00.txt"]["com_sua_voz"] is False


def test_html_dropdown_marca_com_sua_voz():
    assert "com sua voz" in HTML
    inicio = HTML.find("function buildSelectOptions")
    bloco = HTML[inicio : inicio + 900]
    assert "com_sua_voz" in bloco