# -*- coding: utf-8 -*-
"""T-15.B1 / FR-15.B1 (leitura) — idioma da legenda: envelope, ponte, Diagnóstico e alinhamento."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from sessao_reuniao import EnvelopeRejeitado, criar_sessao, validar_envelope

sys.path.insert(0, str(Path(__file__).parent))


def _sessao():
    return criar_sessao("reuniao-b1", "2026-09-19T20:00:00Z", "padrao")


def _envelope(s, kind="capabilities", schema=2, **extra):
    ev = {"schema_version": schema, "event_id": "e1", "session_id": s.session_id, "connection_id": "c1",
          "seq": 0, "tab_id": "aba-1", "meeting_key": s.meeting_key, "kind": kind,
          "client_wall_ms": 1_789_848_060_000, "client_monotonic_ms": 1, "received_monotonic_ns": 1}
    ev.update(extra)
    return ev


@pytest.mark.parametrize("campo", ["caption_lang", "lang_requested"])
def test_idioma_valido_aceito_e_lixo_rejeitado(campo):
    s = _sessao()
    assert validar_envelope(_envelope(s, **{campo: "pt-BR"}), s)[campo] == "pt-BR"
    for ruim in ("pt", "<b>", "pt-BR-x", 3):
        with pytest.raises(EnvelopeRejeitado, match=campo):
            validar_envelope(_envelope(s, **{campo: ruim}), s)


def test_ponte_lembra_o_idioma_observado(chave_teste, tmp_path):
    from eventos_meet_store import EventStore
    from meet_bridge import MeetBridge

    bridge = MeetBridge()
    s = _sessao()
    store = EventStore(tmp_path / "ev", s)
    bridge.registrar_hello({"tipo": "hello", "connection_id": "c1", "tab_id": "aba-1",
                            "meeting_hint": "abc-defg-hij", "active": True})
    bridge.definir_sessao_ativa(s, store, meeting_hint="abc-defg-hij")
    bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")
    assert bridge.idiomas_meet == {}
    bridge.registrar_envelope("c1", _envelope(s, caption_lang="en-US", lang_requested="en-US"))
    assert bridge.idiomas_meet == {"caption_lang": "en-US", "lang_requested": "en-US"}


def _item_idioma(itens):
    return [i for i in itens if i["nome"] == "Idioma da legenda do Meet"]


def test_diagnostico_aponta_divergencia():
    import diagnostico

    item = _item_idioma(diagnostico.checar_idioma_legenda({"caption_lang": "en-US"}, "pt"))[0]
    assert item["estado"] == diagnostico.AVISO
    assert "en-US" in item["detalhe"] and "pt" in item["detalhe"]


def test_diagnostico_idioma_igual_ou_ausente():
    import diagnostico

    assert _item_idioma(diagnostico.checar_idioma_legenda({"caption_lang": "pt-BR"}, "pt"))[0]["estado"] == diagnostico.OK
    assert diagnostico.checar_idioma_legenda({}, "pt") == []
    assert diagnostico.checar_idioma_legenda({"caption_lang": "en-US"}, "auto")[0]["estado"] == diagnostico.OK


def test_linha_do_tempo_guarda_idioma_da_revisao_mais_nova():
    from linha_tempo_falas import construir_linha_tempo

    base = {"kind": "caption", "caption_id": "rtc-1/dev-1", "participant_id": "dev-1", "ts_sec": 1.0}
    falas = construir_linha_tempo([{**base, "caption_revision": 1, "caption_lang": "en-US", "text": "a"},
                                   {**base, "caption_revision": 2, "caption_lang": "pt-BR", "text": "b"}])
    assert falas[0].idioma == "pt-BR"


def test_idioma_divergente_zera_peso_textual():
    """Legenda em inglês numa transcrição em português: o texto não pode ancorar nada."""
    from alinhador_falas import alinhar_segmentos
    from test_alinhador_falas import reuniao_sintetica

    segmentos, eventos, _ = reuniao_sintetica(11, 3, atraso_ms=1000)
    mesmo = alinhar_segmentos(segmentos, eventos, incerteza_ms=10, idioma_transcricao="pt")
    for ev in eventos:
        ev["caption_lang"] = "en-US"
    outro = alinhar_segmentos(segmentos, eventos, incerteza_ms=10, idioma_transcricao="pt")
    assert mesmo.alinhamento["estimado"] is True and mesmo.alinhamento["idioma_divergente"] is False
    assert outro.alinhamento["estimado"] is False
    assert outro.alinhamento["idioma_legenda"] == "en-US" and outro.alinhamento["idioma_divergente"] is True
    medias = [sum(a.score for a in r.atribuicoes.values() if a.score) / len(r.atribuicoes) for r in (mesmo, outro)]
    assert medias[1] < medias[0]
    assert any(a.display_name for a in outro.atribuicoes.values())
