# -*- coding: utf-8 -*-
"""Testes do módulo detector_meet (baseline F0)."""
import pytest

from detector_meet import DetectorMeet, titulo_eh_meet


@pytest.mark.parametrize(
    "titulo,esperado",
    [
        ("Reuniao de equipe - Google Meet", True),
        ("Daily standup - Google Meet", True),
        ("Daily - Google Meet - Google Chrome", True),
        ("Planejamento - Google Meet — Microsoft\u200b Edge", True),
        ("Planejamento - Google Meet - Perfil 1 — Microsoft Edge", True),
        ("meet.google.com/abc-defg-hij", True),
        ("como usar google meet - Pesquisa Google", False),
        ("Novidades do Google Meet - Google Chrome", False),
        ("como configurar Google Meet - Pesquisa Google", False),
        ("Google Meet Help - Google Chrome", False),
        ("Google Meet - Sign in", False),
        ("tutorial google meet ajuda", False),
        ("", False),
        ("   ", False),
    ],
)
def test_titulo_eh_meet(titulo, esperado):
    assert titulo_eh_meet(titulo) is esperado


def test_debounce_inicio_requer_ciclos_consecutivos():
    d = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    titulos = ["Equipe - Google Meet"]
    assert d.verificar(titulos) is None
    assert d.meet_ativo is False
    assert d.verificar(titulos) == "iniciou"
    assert d.meet_ativo is True


def test_debounce_fim_requer_ausencias_consecutivas():
    d = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    meet = ["Sprint - Google Meet"]
    d.verificar(meet)
    d.verificar(meet)
    assert d.meet_ativo is True
    assert d.verificar([]) is None
    assert d.verificar([]) is None
    assert d.verificar([]) == "encerrou"
    assert d.meet_ativo is False


def test_verificar_sem_mudanca_enquanto_meet_ativo():
    d = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    meet = ["Projeto - Google Meet"]
    d.verificar(meet)
    d.verificar(meet)
    assert d.meet_ativo is True
    assert d.verificar(meet) is None
    assert d.meet_ativo is True
