# -*- coding: utf-8 -*-
"""T-15.C2 — linha do tempo de falas a partir dos eventos convertidos."""
from __future__ import annotations

import pytest

from linha_tempo_falas import construir_linha_tempo

MS = 1_000_000


def _legenda(caption_id, revisao, inicio_s, fim_s=None, *, pid="dev-1", nome="Ana", texto="bom dia", eid=None):
    ev = {"kind": "caption", "caption_id": caption_id, "caption_revision": revisao,
          "participant_id": pid, "display_name": nome, "text": texto,
          "event_id": eid or f"{caption_id}#{revisao}", "ts_sec": inicio_s}
    if fim_s is not None:
        ev["ts_fim_sec"] = fim_s
    return ev


def test_revisoes_viram_uma_fala():
    falas = construir_linha_tempo([
        _legenda("rtc-6/dev-1", 1, 10.0, 10.4, texto="vamos"),
        _legenda("rtc-6/dev-1", 3, 10.1, 12.2, texto="vamos revisar o cronograma"),
        _legenda("rtc-6/dev-1", 2, 10.05, 11.0, texto="vamos revisar"),
    ])
    assert len(falas) == 1
    fala = falas[0]
    assert (fala.inicio_ms, fala.fim_ms) == (10_000, 12_200)
    assert fala.texto == "vamos revisar o cronograma"
    assert fala.participant_id == "dev-1" and fala.nome == "Ana"
    assert set(fala.evento_ids) == {"rtc-6/dev-1#1", "rtc-6/dev-1#2", "rtc-6/dev-1#3"}


def test_sem_relogio_retorna_vazio():
    ev = _legenda("rtc-1/dev-1", 1, 1.0)
    del ev["ts_sec"]
    assert construir_linha_tempo([ev]) == []


def test_ignora_nao_legenda_e_sem_participante():
    sem_pid = _legenda("rtc-2/dev-2", 1, 2.0)
    sem_pid["participant_id"] = None
    eventos = [{"kind": "heartbeat", "ts_sec": 1.0}, sem_pid, _legenda("rtc-3/dev-3", 1, 3.0, pid="dev-3")]
    assert [f.participant_id for f in construir_linha_tempo(eventos)] == ["dev-3"]


def test_nome_de_qualquer_revisao_e_ordem_por_inicio():
    sem_nome = _legenda("rtc-9/dev-2", 2, 5.0, 6.0, pid="dev-2", nome="", texto="depois")
    com_nome = _legenda("rtc-9/dev-2", 1, 5.0, 5.5, pid="dev-2", nome="Bruno", texto="dep")
    antes = _legenda("rtc-8/dev-1", 1, 1.0, 2.0)
    falas = construir_linha_tempo([sem_nome, com_nome, antes])
    assert [f.fala_id for f in falas] == ["rtc-8/dev-1", "rtc-9/dev-2"]
    assert falas[1].nome == "Bruno" and falas[1].texto == "depois"


def test_sem_fim_usa_inicio():
    fala = construir_linha_tempo([_legenda("rtc-4/dev-1", 1, 4.0)])[0]
    assert fala.fim_ms == fala.inicio_ms == 4000


def test_relogio_converte_tambem_o_fim_da_fala():
    from relogio_meet import eventos_no_tempo_do_audio

    ev = {"kind": "caption", "speech_started_monotonic_ns": 12_000 * MS,
          "speech_last_monotonic_ns": 14_500 * MS, "clock_uncertainty_ms": 3.0}
    convertido, _ = eventos_no_tempo_do_audio([ev], 10_000 * MS)
    assert convertido[0]["ts_sec"] == pytest.approx(2.0)
    assert convertido[0]["ts_fim_sec"] == pytest.approx(4.5)
