# -*- coding: utf-8 -*-
"""Pareamento da extensão Meet sobrevive a reinícios do app (decisão do usuário, 24/09/2026)."""
from __future__ import annotations

import json

import pytest

import meet_pareamento
from meet_pareamento import ConviteInvalido, Pareador

DIA = 86400.0


@pytest.fixture
def relogio(monkeypatch):
    agora = {"t": 1_800_000_000.0}
    monkeypatch.setattr(meet_pareamento.time, "time", lambda: agora["t"])
    return agora


def _parear(pareador: Pareador) -> str:
    token, era_convite = pareador.autenticar(pareador.gerar_convite())
    assert era_convite
    return token


def test_credencial_sobrevive_a_novo_pareador(tmp_path, relogio):
    arquivo = tmp_path / "meet_pareamento.json"
    token = _parear(Pareador(arquivo=arquivo))
    reiniciado = Pareador(arquivo=arquivo)
    assert reiniciado.autenticar(token) == (token, False)


def test_arquivo_guarda_so_hash(tmp_path, relogio):
    arquivo = tmp_path / "meet_pareamento.json"
    token = _parear(Pareador(arquivo=arquivo))
    conteudo = arquivo.read_text(encoding="utf-8")
    assert token not in conteudo
    assert "pair-" not in conteudo
    json.loads(conteudo)


def test_expira_sem_uso_e_renova_com_uso(tmp_path, relogio):
    arquivo = tmp_path / "meet_pareamento.json"
    pareador = Pareador(arquivo=arquivo, validade_sessao_seg=90 * DIA)
    token = _parear(pareador)
    relogio["t"] += 80 * DIA
    assert Pareador(arquivo=arquivo).validar_token(token)  # uso renova
    relogio["t"] += 80 * DIA
    assert Pareador(arquivo=arquivo).validar_token(token)
    relogio["t"] += 91 * DIA
    with pytest.raises(ConviteInvalido):
        Pareador(arquivo=arquivo).autenticar(token)


def test_revogacao_persiste(tmp_path, relogio):
    arquivo = tmp_path / "meet_pareamento.json"
    pareador = Pareador(arquivo=arquivo)
    token = _parear(pareador)
    pareador.revogar_token(token)
    assert not Pareador(arquivo=arquivo).validar_token(token)


def test_limite_de_credenciais_descarta_a_mais_antiga(tmp_path, relogio):
    arquivo = tmp_path / "meet_pareamento.json"
    pareador = Pareador(arquivo=arquivo)
    tokens = []
    for _ in range(Pareador.MAX_SESSOES + 1):
        tokens.append(_parear(pareador))
        relogio["t"] += 1
    novo = Pareador(arquivo=arquivo)
    assert not novo.validar_token(tokens[0])
    assert all(novo.validar_token(t) for t in tokens[1:])


def test_arquivo_corrompido_nao_derruba(tmp_path, relogio):
    arquivo = tmp_path / "meet_pareamento.json"
    arquivo.write_text("{nao json", encoding="utf-8")
    pareador = Pareador(arquivo=arquivo)
    token = _parear(pareador)
    assert Pareador(arquivo=arquivo).validar_token(token)


def test_sem_arquivo_nao_escreve_nada(tmp_path, relogio, monkeypatch):
    vazio = tmp_path / "cwd"
    vazio.mkdir()
    monkeypatch.chdir(vazio)
    token = _parear(Pareador())
    assert list(vazio.iterdir()) == []
    assert not Pareador().validar_token(token)


def test_convite_continua_de_uso_unico(tmp_path, relogio):
    pareador = Pareador(arquivo=tmp_path / "p.json")
    convite = pareador.gerar_convite()
    pareador.autenticar(convite)
    with pytest.raises(ConviteInvalido):
        pareador.autenticar(convite)
