# -*- coding: utf-8 -*-
"""T-13.G3 — métricas penalizam erro, reconhecem abstinência, roster não é fala."""
from __future__ import annotations

from scripts.avaliar_qualidade_reuniao import (
    der,
    intervalo_wilson,
    metricas_nominais,
    wer,
)


def test_wer_penaliza_substituicao_com_valor_esperado():
    assert wer("a b c d", "a x c") == 0.5
    assert wer("bom dia", "bom dia") == 0.0


def test_nome_incorreto_penaliza_precisao():
    pares = [
        ({"nome": "Ana", "status": "confirmed"}, "Ana"),
        ({"nome": "Bruno", "status": "confirmed"}, "Carla"),
    ]
    rel = metricas_nominais(pares)
    assert rel["precisao_seletiva"] == 0.5


def test_abstinencia_nao_e_erro():
    pares = [
        ({"nome": "Ana", "status": "confirmed"}, "Ana"),
        ({"nome": None, "status": "unknown"}, "Bruno"),
    ]
    rel = metricas_nominais(pares)
    assert rel["precisao_seletiva"] == 1.0
    assert rel["abstencoes"] == 1
    assert rel["cobertura_elegivel"] == 0.5


def test_roster_sozinho_nao_nomeia():
    pares = [
        ({"nome": "Ana", "status": "roster", "roster_sem_fala": True}, "Ana"),
    ]
    rel = metricas_nominais(pares)
    assert rel["corretos"] == 0
    assert rel["cobertura_total"] == 0.0


def test_der_tempo_com_politica_declarada():
    ref = [{"inicio": 0.0, "fim": 10.0, "falante": "A"}]
    hyp = [{"inicio": 0.0, "fim": 10.0, "falante": "B"}]
    assert der(ref, hyp, politica_sobreposicao="perdoar") == 1.0
    assert der(ref, hyp, politica_sobreposicao="rigorosa") == 1.0
    assert der(ref, ref, politica_sobreposicao="perdoar") == 0.0


def test_ic95_contem_taxa():
    lo, hi = intervalo_wilson(98, 100)
    assert lo < 0.98 <= hi
    lo, hi = intervalo_wilson(0, 0)
    assert (lo, hi) == (0.0, 0.0)
