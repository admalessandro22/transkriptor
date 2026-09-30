# -*- coding: utf-8 -*-
"""T-15.B4 / NFR-15.B4 — saúde do canal de legendas no Diagnóstico, sem conteúdo."""
from __future__ import annotations

import pytest

from sessao_reuniao import EnvelopeRejeitado, criar_sessao, validar_envelope


def _sessao():
    return criar_sessao("reuniao-b4", "2026-09-19T20:00:00Z", "padrao")


def _saude(s, **extra):
    ev = {"schema_version": 2, "event_id": "h1", "session_id": s.session_id, "connection_id": "c1", "seq": 0,
          "tab_id": "aba-1", "meeting_key": s.meeting_key, "kind": "health", "client_wall_ms": 1_789_848_060_000,
          "client_monotonic_ms": 1, "received_monotonic_ns": 1,
          "raw": 10, "parsed": 9, "rejected": 1, "recriacoes": 0, "quedas": 0, "motivos": {"decodificacao": 1},
          "esqueleto": "1:LEN(23){1:VARINT 2:LEN(19)}", "build_meet": "2026.09.21_00_RC00", "tactiq": False}
    ev.update(extra)
    return ev


def test_envelope_de_saude_valido():
    s = _sessao()
    assert validar_envelope(_saude(s), s)["parsed"] == 9


@pytest.mark.parametrize("campo,valor", [
    ("raw", -1), ("parsed", "9"), ("motivos", {"<script>": 1}), ("esqueleto", "segredo: 'texto'"),
    ("build_meet", "a b"), ("tactiq", "sim"),
])
def test_saude_so_aceita_numeros_e_marcadores(campo, valor):
    s = _sessao()
    with pytest.raises(EnvelopeRejeitado):
        validar_envelope(_saude(s, **{campo: valor}), s)


def test_ponte_guarda_a_ultima_saude(chave_teste, tmp_path):
    from eventos_meet_store import EventStore
    from meet_bridge import MeetBridge

    bridge = MeetBridge()
    s = _sessao()
    bridge.registrar_hello({"tipo": "hello", "connection_id": "c1", "tab_id": "aba-1",
                            "meeting_hint": "abc-defg-hij", "active": True})
    bridge.definir_sessao_ativa(s, EventStore(tmp_path / "ev", s), meeting_hint="abc-defg-hij")
    bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")
    assert bridge.saude_meet == {}
    bridge.registrar_envelope("c1", _saude(s))
    assert bridge.saude_meet["parsed"] == 9 and bridge.saude_meet["build_meet"] == "2026.09.21_00_RC00"


def _item(itens):
    return [i for i in itens if i["nome"] == "Canal de legendas do Meet"]


def test_motivo_canal_nunca_abriu():
    import diagnostico

    item = _item(diagnostico.checar_canal_legendas({"raw": 0, "parsed": 0, "rejected": 0}))[0]
    assert item["estado"] == diagnostico.AVISO and "não recebeu" in item["detalhe"]


def test_motivo_formato_mudou_com_build():
    import diagnostico

    item = _item(diagnostico.checar_canal_legendas(
        {"raw": 50, "parsed": 0, "rejected": 50, "build_meet": "2026.10.01_00_RC01"}))[0]
    assert item["estado"] == diagnostico.AVISO and "2026.10.01_00_RC01" in item["detalhe"]


def test_saudavel_e_coexistencia_com_tactiq():
    import diagnostico

    assert diagnostico.checar_canal_legendas({}) == []
    ok = _item(diagnostico.checar_canal_legendas({"raw": 120, "parsed": 118, "rejected": 2, "recriacoes": 1}))[0]
    assert ok["estado"] == diagnostico.OK and "118" in ok["detalhe"] and "recriado 1" in ok["detalhe"]
    tactiq = diagnostico.checar_canal_legendas({"raw": 5, "parsed": 5, "rejected": 0, "tactiq": True})
    assert any(i["nome"] == "Outra extensão de transcrição" and i["estado"] == diagnostico.AVISO for i in tactiq)


def test_resumo_sem_pii():
    import diagnostico

    texto = repr(diagnostico.checar_canal_legendas(
        {"raw": 3, "parsed": 0, "rejected": 3, "esqueleto": "1:LEN(23){1:VARINT 2:LEN(19)}"}))
    assert "segredo" not in texto and "Ana" not in texto
