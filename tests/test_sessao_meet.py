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
        "schema_version": 1,
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


def test_duas_abas_no_mesmo_socket_mantem_estado_independente():
    sessao = _sessao()
    registro = SessoesAtivas()
    registro.vincular("c1", "aba-1", sessao)
    registro.vincular("c2", "aba-2", sessao)
    assert registro.aceitar_evento("c1", _envelope(sessao, conexao="c1", aba="aba-1"))["seq"] == 0
    assert registro.aceitar_evento("c2", _envelope(sessao, conexao="c2", aba="aba-2", event_id="e2"))["seq"] == 0
    with pytest.raises(EnvelopeRejeitado, match="aba"):
        registro.aceitar_evento("c1", _envelope(sessao, seq=1, event_id="e3", conexao="c1", aba="aba-2"))
    with pytest.raises(EnvelopeRejeitado, match="sessão"):
        registro.aceitar_evento("c1", _envelope(_sessao("outra"), seq=1, event_id="e4", conexao="c1", aba="aba-1"))


def test_inicio_real_do_mixin_vincula_sessao_ao_hint_unico(tmp_path, monkeypatch):
    import threading
    from types import SimpleNamespace

    import app_ciclo_reuniao
    import config
    from app_ciclo_reuniao import CicloReuniaoMixin
    from meet_bridge import MeetBridge

    monkeypatch.setattr(config, "PASTA_TRANSCRICOES", str(tmp_path))
    monkeypatch.setattr(app_ciclo_reuniao, "PASTA_TRANSCRICOES", str(tmp_path))
    monkeypatch.setattr(app_ciclo_reuniao, "Watchdog", lambda *a, **k: SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(app_ciclo_reuniao, "notificar", lambda *a, **k: None)

    class App(CicloReuniaoMixin):
        def __init__(self):
            self._lock = threading.Lock()
            self.deteccao_ativa = True
            self.detector = SimpleNamespace(fontes_da_reuniao=["extensao"],
                                            chave_reuniao_atual=lambda: "chave-opaca",
                                            titulo_reuniao_atual=lambda: None)
            self.meet_bridge = MeetBridge()
            self.meet_bridge.registrar_hello({"tipo": "hello", "connection_id": "c1",
                                              "tab_id": "aba-1", "meeting_hint": "abc-defg-hij", "active": True})
            self.transcritor = None

        def _status(self, _mensagem):
            pass

        def _construir_transcritor(self):
            return SimpleNamespace(start=lambda: None, rodando=True)

        def _atualizar_tooltip(self):
            pass

    app = App()
    app._iniciar_transcricao_interno()
    assert app._sessao_ativa is not None
    assert app.meet_bridge._sessao_ativa.session_id == app._sessao_ativa.session_id
    assert app.meet_bridge._meeting_hint_ativo == "abc-defg-hij"


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


def test_envelope_v1_rejeita_versao_ausente_ou_desconhecida():
    sessao = _sessao()
    evento = _envelope(sessao)
    for versao in (None, 2, "1"):
        candidato = {**evento, "schema_version": versao}
        with pytest.raises(EnvelopeRejeitado, match="schema_version"):
            validar_envelope(candidato, sessao)


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
