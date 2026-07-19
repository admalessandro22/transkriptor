# -*- coding: utf-8 -*-
"""Testes de estado do ícone da bandeja (Fase 2 — FR-2.1/2.2)."""
from types import SimpleNamespace

from estado_icone import (
    COR_AGUARDANDO,
    COR_PAUSADO,
    DURACAO_ERRO_ICONE,
    cor_por_estado,
    erro_icone_expirado,
    resolver_estado_icone,
)


def test_erro_critico_retorna_estado_erro():
    estado, titulo = resolver_estado_icone(None, True, em_erro=True, instante_erro=100.0, agora=110.0)
    assert estado == "erro"
    assert titulo == "Erro"


def test_erro_reverte_apos_duracao():
    assert erro_icone_expirado(0.0, DURACAO_ERRO_ICONE + 1, duracao=DURACAO_ERRO_ICONE) is True
    assert erro_icone_expirado(0.0, 10.0, duracao=DURACAO_ERRO_ICONE) is False


def test_erro_expirado_volta_para_aguardando():
    estado, _ = resolver_estado_icone(None, True, em_erro=True, instante_erro=0.0, agora=DURACAO_ERRO_ICONE + 5)
    assert estado == "aguardando"


def test_pausado_usa_cor_distinta_de_aguardando():
    assert cor_por_estado("pausado") == COR_PAUSADO
    assert cor_por_estado("aguardando") == COR_AGUARDANDO
    assert COR_PAUSADO != COR_AGUARDANDO
    assert COR_PAUSADO == (100, 116, 139)


def test_pausado_quando_deteccao_inativa():
    estado, titulo = resolver_estado_icone(None, deteccao_ativa=False)
    assert estado == "pausado"
    assert "PAUSADO" in titulo
    assert "não está gravando" in titulo or "nao esta gravando" in titulo.lower()


def test_transcrevendo_prioridade_sobre_pausado():
    t = SimpleNamespace(rodando=True, diarizando=False)
    estado, titulo = resolver_estado_icone(t, deteccao_ativa=False)
    assert estado == "transcrevendo"
    assert titulo == "Transcrevendo"


def test_app_inicia_com_deteccao_ativa(modulo_transkriptor, monkeypatch):
    """FR-2.7: pausa não persiste — novo App sempre com detecção ativa."""
    monkeypatch.setattr(modulo_transkriptor, "chave_disponivel", lambda: False)
    monkeypatch.setattr(modulo_transkriptor, "perfil_existe", lambda *a, **k: False)
    monkeypatch.setattr(modulo_transkriptor, "_carregar_config_user", lambda: {})
    monkeypatch.setattr(modulo_transkriptor, "sincronizar_token_extensao", lambda *a, **k: None)
    app = modulo_transkriptor.AppTranskriptor()
    assert app.deteccao_ativa is True


def test_pausar_sem_confirmar_nao_pausa(modulo_transkriptor, monkeypatch):
    """FR-2.6: sem confirmação, detecção permanece ativa."""
    monkeypatch.setattr(modulo_transkriptor, "chave_disponivel", lambda: False)
    monkeypatch.setattr(modulo_transkriptor, "perfil_existe", lambda *a, **k: False)
    monkeypatch.setattr(modulo_transkriptor, "_carregar_config_user", lambda: {})
    monkeypatch.setattr(modulo_transkriptor, "sincronizar_token_extensao", lambda *a, **k: None)
    app = modulo_transkriptor.AppTranskriptor()
    app._confirmar_pausa = lambda: False
    app.alternar_deteccao()
    assert app.deteccao_ativa is True
    app._confirmar_pausa = lambda: True
    app.alternar_deteccao()
    assert app.deteccao_ativa is False


def test_toast_meet_em_pausa_unico():
    from transkriptor_acoes import deve_toast_meet_em_pausa, texto_deteccao_menu

    assert deve_toast_meet_em_pausa(False, "iniciou", False) is True
    assert deve_toast_meet_em_pausa(False, "iniciou", True) is False
    assert deve_toast_meet_em_pausa(True, "iniciou", False) is False
    assert "NÃO grava" in texto_deteccao_menu(True)