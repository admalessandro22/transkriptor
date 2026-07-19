# -*- coding: utf-8 -*-
"""Testes de janela visível no detector Meet (Fase 5 — FR-5.2)."""
import pytest

from detector_meet import DetectorMeet, titulo_eh_meet


def test_titulo_minimizado_ignorado_com_flag():
    titulo = "Equipe - Google Meet"
    assert titulo_eh_meet(titulo, visivel=False, exigir_janela_visivel=True) is False
    assert titulo_eh_meet(titulo, visivel=True, exigir_janela_visivel=True) is True


def test_titulo_minimizado_aceito_sem_flag():
    titulo = "Equipe - Google Meet"
    assert titulo_eh_meet(titulo, visivel=False, exigir_janela_visivel=False) is True


def test_detector_nao_confirma_meet_em_janela_minimizada():
    d = DetectorMeet(confirma_inicio=1, confirma_fim=1, exigir_janela_visivel=True)
    janelas = [{"titulo": "Daily - Google Meet", "visivel": False}]
    assert d.verificar_janelas(janelas) is None
    assert d.meet_ativo is False


def test_detector_confirma_meet_em_janela_visivel():
    d = DetectorMeet(confirma_inicio=1, confirma_fim=1, exigir_janela_visivel=True)
    janelas = [{"titulo": "Daily - Google Meet", "visivel": True}]
    assert d.verificar_janelas(janelas) == "iniciou"
    assert d.meet_ativo is True