# -*- coding: utf-8 -*-
"""FR-14.D2 — configurações na Central com as regras do menu (T-14.D2)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from assistente import COOKIE_TOKEN, HEADER_TOKEN, app, obter_token_sessao


class AppFalso:
    """Mesmas funções do MenuBandejaMixin, com registro do que foi chamado."""

    def __init__(self):
        self.deteccao_ativa = True
        self.diarizacao_ativa = True
        self.identificar_minha_voz = False
        self.usar_nomes_meet = False
        self.modo_legendas_meet = False
        self.criptografar_transcricoes = True
        self.modelo_whisper = "auto"
        self.iniciar_com_windows = False
        self.chamadas = []

    def alternar_deteccao(self, _icone=None, _item=None):
        self.alternar_deteccao_com()

    def alternar_deteccao_com(self, confirmar=None):
        if self.deteccao_ativa and confirmar is not None and not confirmar():
            return
        self.deteccao_ativa = not self.deteccao_ativa
        self.chamadas.append(("deteccao", self.deteccao_ativa))

    def alternar_diarizacao(self, *_a):
        self.diarizacao_ativa = not self.diarizacao_ativa
        self.chamadas.append(("diarizacao", self.diarizacao_ativa))

    def alternar_identificar_voz(self, *_a):
        self.identificar_minha_voz = not self.identificar_minha_voz

    def alternar_nomes_meet(self, *_a):
        self.usar_nomes_meet = not self.usar_nomes_meet

    def alternar_legendas_meet(self, *_a):
        self.modo_legendas_meet = not self.modo_legendas_meet
        self.usar_nomes_meet = True

    def alternar_criptografia(self, *_a):
        self.criptografar_transcricoes = not self.criptografar_transcricoes

    def alternar_startup(self, *_a):
        self.iniciar_com_windows = not self.iniciar_com_windows

    def definir_modelo_whisper(self, _icone=None, modelo=None):
        self.modelo_whisper = modelo
        self.chamadas.append(("modelo", modelo))

    def ativar_modo_protegido(self, _icone=None, _item=None):
        self.ativar_modo_protegido_com()

    def ativar_modo_protegido_com(self, confirmar=None):
        if confirmar is not None and not confirmar():
            return
        self.chamadas.append(("protegido", True))

    def apagar_perfil_voz(self, *_a):
        self.chamadas.append(("apagar_perfil", True))


@pytest.fixture()
def bandeja(monkeypatch):
    import central_config

    falso = AppFalso()
    central_config.registrar_app(falso)
    monkeypatch.setattr("politica_privacidade.modo_efetivo", lambda: SimpleNamespace(value="compatible"))
    monkeypatch.setattr("crypto_storage.perfil_existe", lambda *_a: False)
    yield falso
    central_config.registrar_app(None)


@pytest.fixture()
def cliente():
    app.config["TESTING"] = True
    return app.test_client()


def _h():
    return {HEADER_TOKEN: obter_token_sessao()}


def test_config_get_espelha_a_bandeja(cliente, bandeja):
    dados = cliente.get("/api/config", headers=_h()).get_json()
    assert dados["deteccao_ativa"] is True and dados["protection_mode"] == "compatible"
    assert dados["modelos_whisper"][0] == "auto" and dados["perfil_voz_existe"] is False
    assert set(dados) >= {"deteccao_ativa", "diarizacao_ativa", "identificar_minha_voz", "usar_nomes_meet", "modo_legendas_meet", "criptografar_transcricoes", "protection_mode", "modelo_whisper", "iniciar_com_windows", "perfil_voz_existe"}


def test_config_503_sem_bandeja(cliente):
    import central_config

    central_config.registrar_app(None)
    assert cliente.get("/api/config", headers=_h()).status_code == 503
    assert cliente.post("/api/config", json={"chave": "diarizacao_ativa", "valor": False}, headers=_h()).status_code == 503


def test_config_post_exige_header_secreto(cliente, bandeja):
    cliente.set_cookie(COOKIE_TOKEN, obter_token_sessao())
    assert cliente.post("/api/config", json={"chave": "diarizacao_ativa", "valor": False}).status_code == 403


def test_pausar_sem_confirmacao_409_com_consequencia(cliente, bandeja):
    resposta = cliente.post("/api/config", json={"chave": "deteccao_ativa", "valor": False}, headers=_h())
    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["acao"] == "pausar_gravacao" and "NÃO grava" in corpo["consequencia"]
    assert bandeja.deteccao_ativa is True
    resposta = cliente.post("/api/config", json={"chave": "deteccao_ativa", "valor": False, "confirmado": True}, headers=_h())
    assert resposta.status_code == 200 and resposta.get_json()["deteccao_ativa"] is False
    # retomar não exige confirmação
    assert cliente.post("/api/config", json={"chave": "deteccao_ativa", "valor": True}, headers=_h()).get_json()["deteccao_ativa"] is True


def test_toggle_usa_a_mesma_funcao_do_menu_e_e_idempotente(cliente, bandeja):
    cliente.post("/api/config", json={"chave": "diarizacao_ativa", "valor": False}, headers=_h())
    cliente.post("/api/config", json={"chave": "diarizacao_ativa", "valor": False}, headers=_h())
    assert bandeja.chamadas.count(("diarizacao", False)) == 1
    assert bandeja.diarizacao_ativa is False


def test_modelo_whisper_valida_e_aplica(cliente, bandeja):
    assert cliente.post("/api/config", json={"chave": "modelo_whisper", "valor": "gigante"}, headers=_h()).status_code == 400
    resposta = cliente.post("/api/config", json={"chave": "modelo_whisper", "valor": "small"}, headers=_h())
    assert resposta.status_code == 200 and resposta.get_json()["modelo_whisper"] == "small"


def test_modo_protegido_e_apagar_perfil_exigem_confirmacao(cliente, bandeja):
    assert cliente.post("/api/config", json={"chave": "protection_mode", "valor": "protected"}, headers=_h()).status_code == 409
    assert cliente.post("/api/config", json={"chave": "protection_mode", "valor": "compatible", "confirmado": True}, headers=_h()).status_code == 400
    assert cliente.post("/api/config", json={"chave": "protection_mode", "valor": "protected", "confirmado": True}, headers=_h()).status_code == 200
    assert cliente.post("/api/config", json={"chave": "apagar_perfil_voz"}, headers=_h()).status_code == 409
    assert cliente.post("/api/config", json={"chave": "apagar_perfil_voz", "confirmado": True}, headers=_h()).status_code == 200
    assert ("protegido", True) in bandeja.chamadas and ("apagar_perfil", True) in bandeja.chamadas


def test_chave_desconhecida_400(cliente, bandeja):
    assert cliente.post("/api/config", json={"chave": "senha", "valor": "x"}, headers=_h()).status_code == 400
    assert cliente.post("/api/config", json={"chave": "diarizacao_ativa", "valor": "sim"}, headers=_h()).status_code == 400


def test_menu_da_bandeja_aceita_confirmar_injetado():
    """As funções do menu recebem `confirmar` para a Central não abrir MessageBox."""
    import inspect

    from app_bandeja_menu import MenuBandejaMixin

    # As ações do menu mantêm (icone, item) — o pystray recusa mais parâmetros — e delegam ao `_com`.
    assert list(inspect.signature(MenuBandejaMixin.alternar_deteccao).parameters) == ["self", "_icone", "_item"]
    assert "confirmar" in inspect.signature(MenuBandejaMixin.alternar_deteccao_com).parameters
    assert "confirmar" in inspect.signature(MenuBandejaMixin.ativar_modo_protegido_com).parameters
