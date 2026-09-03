# -*- coding: utf-8 -*-
"""FR-9.C4 — um monitor travado tem de virar alarme, não silêncio.

Em 2026-08-07 a thread do monitor travou às 00:16 e o app ficou três dias na
bandeja com o ícone normal, sem heartbeat e sem erro. O heartbeat só prova vida
quando alguém *lê* o log; o vigia transforma a ausência dele em erro visível.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from config import FATOR_TRAVAMENTO_MONITOR, INTERVALO_MONITOR_MEET
from monitor_reuniao import VigiaMonitor

LIMITE = INTERVALO_MONITOR_MEET * FATOR_TRAVAMENTO_MONITOR


@pytest.fixture
def vigia():
    alarmes = []
    v = VigiaMonitor(on_travado=alarmes.append)
    v.alarmes = alarmes
    return v


def test_monitor_girando_nao_alarma(vigia):
    for segundo in range(0, 100, INTERVALO_MONITOR_MEET):
        vigia.bater(segundo)
        vigia.verificar(segundo)

    assert vigia.alarmes == []


def test_sem_bater_dentro_do_limite_nao_alarma(vigia):
    vigia.bater(0)

    assert vigia.verificar(LIMITE - 1) is False
    assert vigia.alarmes == []


def test_monitor_parado_alarma(vigia):
    vigia.bater(0)

    assert vigia.verificar(LIMITE + 1) is True
    assert len(vigia.alarmes) == 1
    assert "monitor" in vigia.alarmes[0].lower()


def test_alarme_nao_se_repete_a_cada_ciclo(vigia):
    """Um travamento é um alarme, não um toast a cada 5 segundos."""
    vigia.bater(0)
    vigia.verificar(LIMITE + 1)

    for agora in range(LIMITE + 2, LIMITE + 200, INTERVALO_MONITOR_MEET):
        vigia.verificar(agora)

    assert len(vigia.alarmes) == 1


def test_monitor_que_volta_a_girar_rearma_o_vigia(vigia):
    vigia.bater(0)
    vigia.verificar(LIMITE + 1)

    vigia.bater(LIMITE + 2)
    assert vigia.verificar(LIMITE + 3) is False

    assert vigia.verificar(LIMITE * 2 + 10) is True
    assert len(vigia.alarmes) == 2


def test_sem_nenhum_tick_ainda_nao_alarma(vigia):
    """Antes do primeiro ciclo não há o que vigiar."""
    assert vigia.verificar(10_000) is False
    assert vigia.alarmes == []


def test_loop_do_monitor_bate_no_vigia(modulo_transkriptor, monkeypatch):
    """De nada adianta o vigia existir se o monitor não bater nele."""
    app = modulo_transkriptor.AppTranskriptor.__new__(
        modulo_transkriptor.AppTranskriptor
    )
    batidas = []
    app.vigia_monitor = SimpleNamespace(
        bater=lambda agora: batidas.append(agora), verificar=lambda agora: False
    )
    app.deteccao_ativa = True
    app._toast_pausa_reuniao = None
    app._detectar_mudanca_meet = lambda: None
    app._heartbeat_monitor = lambda _ciclos: None
    app._processar_mudanca_meet = lambda _m: None

    class _Parou(Exception):
        pass

    def _sleep(_seg):
        if len(batidas) >= 3:
            raise _Parou

    monkeypatch.setattr(modulo_transkriptor.time, "sleep", _sleep)
    with pytest.raises(_Parou):
        app._monitorar_meet()

    assert len(batidas) == 3


def test_vigia_alarma_pelo_erro_critico_do_app(modulo_transkriptor):
    """O alarme tem de chegar ao usuário, não só ao log."""
    app = modulo_transkriptor.AppTranskriptor.__new__(
        modulo_transkriptor.AppTranskriptor
    )
    criticos = []
    app._erro_critico = criticos.append
    v = VigiaMonitor(on_travado=app._erro_critico)
    v.bater(0)

    v.verificar(LIMITE + 1)

    assert len(criticos) == 1
    assert "monitor" in criticos[0].lower()


def test_falha_no_alarme_nao_derruba_o_vigia(vigia):
    def _explode(_msg):
        raise RuntimeError("toast indisponível")

    v = VigiaMonitor(on_travado=_explode)
    v.bater(0)

    assert v.verificar(LIMITE + 1) is True
