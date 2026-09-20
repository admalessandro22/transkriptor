# -*- coding: utf-8 -*-
"""T-13.D6 — atribuição conservadora: precisão antes de cobertura."""
from __future__ import annotations

from audio_fontes import AudioSource, SegmentoSTT
from identidade_reuniao import (
    AssignmentStatus,
    avaliar_atribuicoes,
    resolver_atribuicao,
)


def _seg(texto, inicio_ms=0, fim_ms=1000, overlap=False):
    return SegmentoSTT("s1", inicio_ms, fim_ms, AudioSource.LOOPBACK, texto, overlap)


def _legenda(nome, texto, ts_sec=0.5, eid="cap-1", pid=None):
    ev = {
        "nome": nome,
        "tipo": "legenda",
        "ts_sec": ts_sec,
        "texto": texto,
        "event_id": eid,
    }
    if pid:
        ev["participant_id"] = pid
    return ev


def test_legenda_sem_match_nao_substitui_voce():
    from correlacionador import aplicar_nomes_meet

    segmentos = [("VOCÊ", 0.0, 1.0, "alpha beta")]
    eventos = [{"nome": "Pessoa remota", "tipo": "legenda",
                "ts_sec": 0.5, "texto": "gamma delta"}]
    assert aplicar_nomes_meet(segmentos, eventos)[0][0] == "VOCÊ"


def test_empate_produz_unknown():
    seg = _seg("vamos revisar o cronograma do projeto")
    eventos = [
        _legenda("Ana", "vamos revisar o cronograma do projeto", ts_sec=0.5, eid="a"),
        _legenda("Bruno", "vamos revisar o cronograma do projeto", ts_sec=0.5, eid="b"),
    ]
    atr = resolver_atribuicao(seg, eventos, clock_uncertainty_ms=100, calibration_version="d6-1")
    assert atr.status in (AssignmentStatus.UNKNOWN, AssignmentStatus.CONFLICT)
    assert atr.display_name is None


def test_homonimos_exigem_id():
    seg = _seg("bom dia a todos")
    eventos = [
        _legenda("Ana", "bom dia a todos", ts_sec=0.5, eid="a", pid="p-111"),
        _legenda("Ana", "bom dia a todos", ts_sec=0.5, eid="b", pid="p-222"),
    ]
    atr = resolver_atribuicao(seg, eventos, clock_uncertainty_ms=100, calibration_version="d6-1")
    assert atr.status in (AssignmentStatus.UNKNOWN, AssignmentStatus.CONFLICT)
    so_um = [dict(e, participant_id="p-111") for e in eventos[:1]]
    atr2 = resolver_atribuicao(seg, so_um, clock_uncertainty_ms=100, calibration_version="d6-1")
    assert atr2.display_name == "Ana"
    assert atr2.participant_id == "p-111"


def test_sobreposicao_nao_forca_um_nome():
    seg = _seg("relatorio final na sexta", overlap=True)
    eventos = [_legenda("Ana", "relatorio final na sexta", ts_sec=0.5)]
    atr = resolver_atribuicao(seg, eventos, clock_uncertainty_ms=100, calibration_version="d6-1")
    assert atr.status in (AssignmentStatus.UNKNOWN, AssignmentStatus.CONFLICT)
    assert atr.display_name is None


def test_evidencia_suficiente_nomeia():
    seg = _seg("vamos revisar o cronograma")
    manual = [{
        "kind": "manual", "display_name": "Ana", "participant_id": "p-1",
        "event_id": "m-1", "segment_id": "s1", "session_id": "s", "connection_id": "c",
        "seq": 0, "tab_id": "t", "meeting_key": "k",
        "client_wall_ms": 1_789_848_060_000, "client_monotonic_ms": 1,
        "received_monotonic_ns": 1,
    }]
    atr = resolver_atribuicao(seg, manual, clock_uncertainty_ms=100, calibration_version="d6-1")
    assert atr.status == AssignmentStatus.CONFIRMED
    assert atr.display_name == "Ana"
    forte = [_legenda("Bruno", "vamos revisar o cronograma", ts_sec=0.5)]
    atr2 = resolver_atribuicao(seg, forte, clock_uncertainty_ms=100, calibration_version="d6-1")
    assert atr2.display_name == "Bruno"
    assert atr2.status == AssignmentStatus.SUGGESTED


def test_relogio_incerto_rebaixa_para_sugestao():
    seg = _seg("vamos revisar o cronograma")
    eventos = [_legenda("Bruno", "vamos revisar o cronograma", ts_sec=0.5)]
    atr = resolver_atribuicao(seg, eventos, clock_uncertainty_ms=5000, calibration_version="d6-1")
    assert atr.status != AssignmentStatus.CONFIRMED


def test_calibracao_publica_metricas():
    from identidade_reuniao import Atribuicao

    pares = [
        (Atribuicao("p-1", "Ana", "manual", 1.0, ("m",), AssignmentStatus.CONFIRMED), "Ana"),
        (Atribuicao("p-2", "Bruno", "caption", 0.9, ("c",), AssignmentStatus.SUGGESTED), "Bruno"),
        (Atribuicao(None, None, "caption", 0.1, (), AssignmentStatus.UNKNOWN), "Carla"),
        (Atribuicao(None, None, "caption", 0.2, (), AssignmentStatus.CONFLICT), None),
    ]
    rel = avaliar_atribuicoes(pares)
    assert rel["precisao_seletiva"] == 1.0
    assert 0.0 < rel["cobertura_elegivel"] <= 1.0
    assert "abstencoes" in rel and rel["abstencoes"] >= 1
