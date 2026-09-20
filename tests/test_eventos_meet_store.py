# -*- coding: utf-8 -*-
"""T-13.D4 — spool cifrado durável, ACK após persistência, sem conteúdo em claro."""
from __future__ import annotations

import datetime
import json
import time
from pathlib import Path

import pytest

from eventos_meet_store import (
    ColetaBloqueada,
    EventStore,
    eventos_elegiveis_exclusao,
)
from sessao_reuniao import criar_sessao


CONSENTIDA = "2026-09-19T20:00:00Z"
WALL_BASE = 1_789_848_060_000


def _sessao(policy="padrao"):
    return criar_sessao("reuniao-d4", CONSENTIDA, policy)


def _evento(sessao, seq, event_id=None, kind="caption", wall=None):
    return {
        "event_id": event_id or f"e-{seq}",
        "session_id": sessao.session_id,
        "connection_id": "c1",
        "seq": seq,
        "tab_id": "aba-1",
        "meeting_key": sessao.meeting_key,
        "kind": kind,
        "client_wall_ms": WALL_BASE + seq * 1000 if wall is None else wall,
        "client_monotonic_ms": 1000 + seq,
        "received_monotonic_ns": time.monotonic_ns(),
        "text": f"fala sintética {seq}",
    }


def _store(tmp_path, chave_teste=None, sessao=None):
    return EventStore(tmp_path / "eventos", sessao or _sessao())


def test_mil_eventos_preserva_o_final(chave_teste, tmp_path):
    """Carga de 1000 eventos: o último está íntegro após dreno contínuo."""
    store = _store(tmp_path, chave_teste)
    for i in range(1000):
        store.append(_evento(store.sessao, i))
    store.descarregar(forcar=True)
    eventos = list(store.read_events())
    assert len(eventos) == 1000
    assert eventos[-1]["event_id"] == "e-999"
    assert store.descartes == 0


def test_ack_exige_durabilidade(chave_teste, tmp_path):
    """ACK só após selo durável: queda antes do dreno perde o prefixo aberto."""
    root = tmp_path / "eventos"
    sessao = _sessao()
    store = EventStore(root, sessao)
    for i in range(5):
        store.append(_evento(sessao, i))
    ack = store.descarregar(forcar=True)
    assert ack == 4
    for i in range(5, 8):
        store.append(_evento(sessao, i))
    del store
    reaberta = EventStore(root, sessao)
    eventos = list(reaberta.read_events())
    assert [e["seq"] for e in eventos] == [0, 1, 2, 3, 4]


def test_crash_recupera_prefixo_integro(chave_teste, tmp_path):
    """Escrita rasgada no último segmento: prefixo selado anterior sobrevive."""
    root = tmp_path / "eventos"
    sessao = _sessao()
    store = EventStore(root, sessao)
    store.append(_evento(sessao, 0))
    store.append(_evento(sessao, 1))
    store.descarregar(forcar=True)
    store.append(_evento(sessao, 2))
    store.append(_evento(sessao, 3))
    store.descarregar(forcar=True)
    # Simula queda no meio da escrita: rasga a cauda do último segmento.
    with open(store._ultimo_segmento_selado, "r+b", buffering=0) as f:
        f.seek(-8, 2)
        f.write(b"\x00" * 8)
    del store
    reaberta = EventStore(root, sessao)
    eventos = list(reaberta.read_events())
    assert [e["seq"] for e in eventos] == [0, 1]
    assert reaberta.descartes >= 1


def test_sem_chave_nao_grava_legenda(chave_teste, tmp_path, monkeypatch):
    """Sem chave disponível, conteúdo é bloqueado; heartbeat segue."""
    import crypto_storage

    monkeypatch.setattr(crypto_storage, "chave_disponivel", lambda: False)
    store = _store(tmp_path, chave_teste)
    with pytest.raises(ColetaBloqueada):
        store.append(_evento(store.sessao, 0))
    ack = store.append(_evento(store.sessao, 0, event_id="hb", kind="heartbeat"))
    assert ack >= -1


def test_revogacao_interrompe_conteudo(chave_teste, tmp_path):
    """Após revogar, nenhuma legenda nova entra; o já selado permanece."""
    store = _store(tmp_path, chave_teste)
    store.append(_evento(store.sessao, 0))
    store.revogar()
    with pytest.raises(ColetaBloqueada):
        store.append(_evento(store.sessao, 1))
    store.descarregar(forcar=True)
    assert [e["seq"] for e in store.read_events()] == [0]


def test_eventos_expiram_so_sete_dias_apos_resultado_valido(chave_teste, tmp_path):
    """Brutos só elegíveis 7 dias após ResultManifest válido."""
    from resultado_reuniao import criar_manifesto_inicial, salvar_manifesto

    raiz = tmp_path / "raiz"
    raiz.mkdir()
    resultado = raiz / "r.txt"
    resultado.write_text("x", encoding="utf-8")
    (raiz / "a.wav").write_bytes(b"0" * 64)
    manifesto = criar_manifesto_inicial(
        meeting_id="m1",
        resultado=resultado,
        fontes_audio=[raiz / "a.wav"],
        raiz=raiz,
        created_at="2026-09-10T12:00:00Z",
    )
    caminho_manifesto = raiz / "m.resultado.json"
    salvar_manifesto(caminho_manifesto, manifesto)
    sessoes = tmp_path / "eventos"
    (sessoes / "sessao-1").mkdir(parents=True)
    antes = datetime.datetime(2026, 9, 16, 12, tzinfo=datetime.timezone.utc)
    depois = datetime.datetime(2026, 9, 18, 12, tzinfo=datetime.timezone.utc)
    assert eventos_elegiveis_exclusao(sessoes, caminho_manifesto, antes) == []
    assert eventos_elegiveis_exclusao(sessoes, caminho_manifesto, depois) != []


def test_job_log_sem_conteudo(chave_teste, tmp_path, caplog):
    """Nomes/textos não vazam para log da coleta."""
    import logging

    store = _store(tmp_path, chave_teste)
    with caplog.at_level(logging.DEBUG):
        store.append(_evento(store.sessao, 0))
        store.descarregar(forcar=True)
    combinado = "\n".join(r.getMessage() for r in caplog.records)
    assert "fala sintética 0" not in combinado
