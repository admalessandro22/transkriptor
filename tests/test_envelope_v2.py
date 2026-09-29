# -*- coding: utf-8 -*-
"""T-15.A1 / FR-15.A1 — envelope schema 2 carrega o tempo da fala."""
from __future__ import annotations

import time

import pytest

from sessao_reuniao import EnvelopeRejeitado, criar_sessao, validar_envelope


def _sessao():
    return criar_sessao("reuniao-a", "2026-09-19T20:00:00Z", "padrao")


def _envelope(sessao, *, schema=2, kind="caption", **extra):
    ev = {
        "schema_version": schema,
        "event_id": "e1",
        "session_id": sessao.session_id,
        "connection_id": "c1",
        "seq": 0,
        "tab_id": "t1",
        "meeting_key": sessao.meeting_key,
        "kind": kind,
        "client_wall_ms": 1_789_848_060_000,
        "client_monotonic_ms": 1000,
        "received_monotonic_ns": time.monotonic_ns(),
    }
    ev.update(extra)
    return ev


def test_v2_legenda_com_tempos_aceita():
    s = _sessao()
    ev = _envelope(
        s, caption_started_ms=1_789_848_059_000.5, caption_last_ms=1_789_848_060_000.0,
        origin_channel="captions_v2",
    )
    aceito = validar_envelope(ev, s)
    assert aceito["caption_started_ms"] == pytest.approx(1_789_848_059_000.5)
    assert aceito["origin_channel"] == "captions_v2"


def test_v2_exige_caption_started():
    s = _sessao()
    with pytest.raises(EnvelopeRejeitado, match="caption_started_ms"):
        validar_envelope(_envelope(s, caption_last_ms=1.0), s)


def test_started_maior_que_last_rejeitado():
    s = _sessao()
    with pytest.raises(EnvelopeRejeitado, match="caption_last_ms"):
        validar_envelope(_envelope(s, caption_started_ms=2000.0, caption_last_ms=1000.0), s)


@pytest.mark.parametrize("valor", ["1000", True, None, float("nan"), float("inf")])
def test_v2_tempo_nao_numerico_rejeitado(valor):
    s = _sessao()
    with pytest.raises(EnvelopeRejeitado):
        validar_envelope(_envelope(s, caption_started_ms=valor, caption_last_ms=1000.0), s)


def test_v2_canal_desconhecido_rejeitado():
    s = _sessao()
    ev = _envelope(s, caption_started_ms=1.0, caption_last_ms=2.0, origin_channel="outro")
    with pytest.raises(EnvelopeRejeitado, match="origin_channel"):
        validar_envelope(ev, s)


def test_v2_heartbeat_sem_tempos_aceito():
    s = _sessao()
    assert validar_envelope(_envelope(s, kind="heartbeat"), s)["schema_version"] == 2


def test_v1_continua_aceito():
    s = _sessao()
    assert validar_envelope(_envelope(s, schema=1), s)["schema_version"] == 1


def test_schema_desconhecida_rejeitada():
    s = _sessao()
    with pytest.raises(EnvelopeRejeitado, match="schema_version"):
        validar_envelope(_envelope(s, schema=3), s)


@pytest.mark.parametrize("campo", ["page_perf_ms", "page_wall_ms"])
def test_amostra_pagina_invalida_rejeitada(campo):
    """T-15.A2: amostra página↔parede, se presente, é número finito."""
    s = _sessao()
    ev = _envelope(s, caption_started_ms=1.0, caption_last_ms=2.0, **{campo: float("nan")})
    with pytest.raises(EnvelopeRejeitado, match=campo):
        validar_envelope(ev, s)
