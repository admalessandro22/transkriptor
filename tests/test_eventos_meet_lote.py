# -*- coding: utf-8 -*-
"""T-15.A3 / FR-15.A3 — eventos do Meet gravados em lote, sem perda nem silêncio."""
from __future__ import annotations

import time

import pytest

import eventos_meet_store
from config import MEET_EVENTOS_DRENO_SEG
from eventos_meet_store import EventStore
from meet_bridge import MeetBridge
from sessao_reuniao import EnvelopeRejeitado, criar_sessao, validar_envelope


class _Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def relogio(monkeypatch):
    r = _Relogio()
    monkeypatch.setattr(eventos_meet_store.time, "monotonic", r)
    return r


def _ponte(tmp_path):
    bridge = MeetBridge()
    sessao = criar_sessao("reuniao-a3", "2026-09-19T20:00:00Z", "padrao")
    store = EventStore(tmp_path / "ev", sessao)
    bridge.registrar_hello({"tipo": "hello", "connection_id": "c1", "tab_id": "aba-1",
                            "meeting_hint": "abc-defg-hij", "active": True})
    bridge.definir_sessao_ativa(sessao, store, meeting_hint="abc-defg-hij")
    bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")
    return bridge, sessao, store


def _ev(sessao, seq, kind="caption", **extra):
    ev = {"schema_version": 1, "event_id": f"e{seq}", "session_id": sessao.session_id, "connection_id": "c1",
          "seq": seq, "tab_id": "aba-1", "meeting_key": sessao.meeting_key, "kind": kind,
          "client_wall_ms": 1_789_848_060_000, "client_monotonic_ms": seq, "received_monotonic_ns": 1}
    if kind == "caption":
        ev.update({"text": f"fala {seq}", "display_name": "Pessoa", "participant_id": "dev-1"})
    ev.update(extra)
    return ev


def _selados(store):
    return len(list(store._segmentos_selados()))


def test_janela_do_lote_e_30s():
    assert MEET_EVENTOS_DRENO_SEG == 30.0


def test_ponte_nao_sela_um_arquivo_por_evento(chave_teste, tmp_path, relogio):
    bridge, sessao, store = _ponte(tmp_path)
    for seq in range(10):
        assert bridge.registrar_envelope("c1", _ev(sessao, seq)) == seq
    assert _selados(store) == 0
    assert len(list(store.read_events())) == 10  # buffer aberto continua legível
    assert bridge.seq_duravel() == -1


def test_lote_lacra_por_tempo_no_heartbeat(chave_teste, tmp_path, relogio):
    """Silêncio depois das falas: o heartbeat fecha o lote quando a janela vence."""
    bridge, sessao, store = _ponte(tmp_path)
    bridge.registrar_envelope("c1", _ev(sessao, 0))
    relogio.t += MEET_EVENTOS_DRENO_SEG + 0.1
    bridge.registrar_envelope("c1", _ev(sessao, 1, kind="heartbeat", active=True))
    assert _selados(store) == 1
    assert bridge.seq_duravel() == 0


def test_lote_lacra_no_fim(chave_teste, tmp_path, relogio):
    bridge, sessao, store = _ponte(tmp_path)
    for seq in range(3):
        bridge.registrar_envelope("c1", _ev(sessao, seq))
    assert len(store.seal()) == 1


def test_idempotente_por_event_id(chave_teste, tmp_path, relogio):
    bridge, sessao, _ = _ponte(tmp_path)
    bridge.registrar_envelope("c1", _ev(sessao, 0))
    with pytest.raises(EnvelopeRejeitado):
        bridge.registrar_envelope("c1", _ev(sessao, 1, event_id="e0"))


def test_aceite_trinta_minutos_seis_pessoas_ate_60_arquivos(chave_teste, tmp_path, relogio):
    """Uma legenda consolidada por segundo durante 30 min, heartbeat a cada 5 s."""
    bridge, sessao, store = _ponte(tmp_path)
    seq = 0
    for segundo in range(30 * 60):
        relogio.t += 1.0
        kind = "heartbeat" if segundo % 5 == 0 else "caption"
        extra = {"active": True} if kind == "heartbeat" else {"participant_id": f"dev-{segundo % 6}"}
        bridge.registrar_envelope("c1", _ev(sessao, seq, kind=kind, **extra))
        seq += 1
    refs = store.seal()
    assert len(refs) <= 60
    assert len([e for e in store.read_events() if e["kind"] == "caption"]) == 30 * 60 - 360


@pytest.mark.parametrize("campo,valor", [("queued", "sim"), ("caption_final", 1)])
def test_marcadores_da_fila_e_da_fala_final_sao_booleanos(campo, valor):
    sessao = criar_sessao("reuniao-a3", "2026-09-19T20:00:00Z", "padrao")
    ok = _ev(sessao, 0, **{campo: True})
    assert validar_envelope(ok, sessao)[campo] is True
    with pytest.raises(EnvelopeRejeitado, match=campo):
        validar_envelope(_ev(sessao, 0, **{campo: valor}), sessao)


def test_descarte_de_taxa_vira_aviso_no_diagnostico():
    import diagnostico

    assert diagnostico.checar_descartes_meet(0) == []
    item = diagnostico.checar_descartes_meet(7)[0]
    assert item["estado"] == diagnostico.AVISO and "7" in item["detalhe"]
