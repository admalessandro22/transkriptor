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
    assert titulo == "Pausado"


def test_transcrevendo_prioridade_sobre_pausado():
    t = SimpleNamespace(rodando=True, diarizando=False)
    estado, titulo = resolver_estado_icone(t, deteccao_ativa=False)
    assert estado == "transcrevendo"
    assert titulo == "Transcrevendo"