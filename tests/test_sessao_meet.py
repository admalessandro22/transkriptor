# -*- coding: utf-8 -*-
"""T-13.D1 — sessão e relógio verificáveis (uma sessão por aba/conexão)."""
from __future__ import annotations

import time

import pytest

import sessao_reuniao
from sessao_reuniao import (
    EnvelopeRejeitado,
    SessoesAtivas,
    anotar_handshake,
    chave_reuniao,
    criar_sessao,
    registrar_primeiro_frame,
    tempo_audio_ms,
    validar_envelope,
)


def _sessao(meeting="reuniao-a", consentida="2026-09-19T20:00:00Z"):
    return criar_sessao(meeting, consentida, "padrao")


def _envelope(sessao, *, seq=0, event_id="e1", conexao="c1", aba="t1", wall_ms=None, kind="caption"):
    return {
        "event_id": event_id,
        "session_id": sessao.session_id,
        "connection_id": conexao,
        "seq": seq,
        "tab_id": aba,
        "meeting_key": sessao.meeting_key,
        "kind": kind,
        "client_wall_ms": wall_ms if wall_ms is not None else 1_789_848_060_000,
        "client_monotonic_ms": 1000 + seq,
        "received_monotonic_ns": time.monotonic_ns(),
    }


def test_duas_abas_nao_se_encerram():
    """Encerrar a conexão de uma aba não mata a sessão da outra."""
    registro = SessoesAtivas()
    s1 = registro.obter_ou_criar("c1", "aba-1", "reuniao-a", "2026-09-19T20:00:00Z", "padrao")
    s2 = registro.obter_ou_criar("c2", "aba-2", "reuniao-b", "2026-09-19T20:00:00Z", "padrao")
    assert s1.session_id != s2.session_id
    registro.encerrar_por_conexao("c1")
    assert registro.ativa("c2") is True
    assert registro.ativa("c1") is False
    ev = _envelope(s2, seq=0, event_id="e-b", conexao="c2", aba="aba-2")
    assert registro.aceitar_evento("c2", ev)["event_id"] == "e-b"


def test_evento_antigo_nao_entra_sessao():
    """Sequência que anda para trás ou event_id repetido é recusado."""
    registro = SessoesAtivas()
    registro.obter_ou_criar("c1", "aba-1", "reuniao-a", "2026-09-19T20:00:00Z", "padrao")
    registro.aceitar_evento("c1", _envelope(registro.sessao_de("c1"), seq=5, event_id="e5", conexao="c1", aba="aba-1"))
    with pytest.raises(EnvelopeRejeitado):
        registro.aceitar_evento("c1", _envelope(registro.sessao_de("c1"), seq=3, event_id="e3", conexao="c1", aba="aba-1"))
    with pytest.raises(EnvelopeRejeitado):
        registro.aceitar_evento("c1", _envelope(registro.sessao_de("c1"), seq=6, event_id="e5", conexao="c1", aba="aba-1"))


def test_mudanca_relogio_nao_desloca_audio():
    """Duração de áudio deriva de frames/sample rate; salto de wall não desloca."""
    antes = tempo_audio_ms(16000, 16000)
    assert antes == 1000
    real_time = time.time
    try:
        time.time = lambda: real_time() + 3600.0
        assert tempo_audio_ms(16000, 16000) == antes
    finally:
        time.time = real_time


def test_evento_antes_do_consentimento_descartado():
    """Evento com client_wall anterior ao consentimento é descartado."""
    sessao = _sessao(consentida="2026-09-19T20:00:00Z")
    ev = _envelope(sessao, wall_ms=1_700_000_000_000)
    with pytest.raises(EnvelopeRejeitado):
        validar_envelope(ev, sessao)


def test_primeiro_frame_fixa_instante_zero():
    """O instante zero é o primeiro frame confirmado; segundo registro não move."""
    sessao = _sessao()
    assert sessao.first_frame_monotonic_ns is None
    s2 = registrar_primeiro_frame(sessao, 123_000_000_000)
    assert s2.first_frame_monotonic_ns == 123_000_000_000
    s3 = registrar_primeiro_frame(s2, 999_000_000_000)
    assert s3.first_frame_monotonic_ns == 123_000_000_000


def test_handshake_incerto_marca_relogio():
    """RTT alto marca relógio incerto em vez de aplicar nomes pelo relógio errado."""
    sessao = _sessao()
    ok = anotar_handshake(sessao, rtt_ms=100.0, offset_ms=20.0)
    assert ok.relogio_incerto is False
    ruim = anotar_handshake(sessao, rtt_ms=4000.0, offset_ms=1500.0)
    assert ruim.relogio_incerto is True


def test_outra_sessao_nao_entra():
    """Envelope de outra sessão/reunião é recusado na sessão atual."""
    s1, s2 = _sessao("reuniao-a"), _sessao("reuniao-b")
    ev = _envelope(s2, conexao="c2", aba="aba-2")
    with pytest.raises(EnvelopeRejeitado):
        validar_envelope(ev, s1)


def test_chave_reuniao_estavel_e_opaca():
    """Mesmo título/fontes geram mesma chave; títulos distintos divergem; sem nome."""
    a = chave_reuniao("Reuniao Bolsistas", ["titulo"])
    b = chave_reuniao("Reuniao Bolsistas", ["titulo"])
    c = chave_reuniao("Outra Reuniao", ["titulo"])
    assert a == b and a != c
    assert "Bolsistas" not in a
