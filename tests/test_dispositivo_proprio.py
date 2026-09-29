# -*- coding: utf-8 -*-
"""T-15.B2 / FR-15.B2 — o dispositivo do próprio usuário vira "<nome> (você)"."""
from __future__ import annotations

import pytest

from alinhador_falas import alinhar_segmentos
from audio_fontes import AudioSource, PalavraSTT, SegmentoSTT
from linha_tempo_falas import dispositivo_proprio
from sessao_reuniao import EnvelopeRejeitado, criar_sessao, validar_envelope


def _sessao():
    return criar_sessao("reuniao-b2", "2026-09-19T20:00:00Z", "padrao")


def _envelope(s, **extra):
    ev = {"schema_version": 2, "event_id": "e1", "session_id": s.session_id, "connection_id": "c1",
          "seq": 0, "tab_id": "aba-1", "meeting_key": s.meeting_key, "kind": "self_device",
          "client_wall_ms": 1_789_848_060_000, "client_monotonic_ms": 1, "received_monotonic_ns": 1}
    ev.update(extra)
    return ev


def test_envelope_self_device_exige_id_de_dispositivo():
    s = _sessao()
    assert validar_envelope(_envelope(s, participant_id="dev-88"), s)["participant_id"] == "dev-88"
    for ruim in (None, "Ana", "dev-", "spaces/x/devices/1"):
        with pytest.raises(EnvelopeRejeitado):
            validar_envelope(_envelope(s, participant_id=ruim), s)


def test_dispositivo_proprio_primeiro_valor():
    eventos = [{"kind": "caption", "participant_id": "dev-1"},
               {"kind": "self_device", "participant_id": "dev-88"},
               {"kind": "self_device", "participant_id": "dev-99"}]
    assert dispositivo_proprio(eventos) == "dev-88"
    assert dispositivo_proprio([]) is None


def _palavras(toks, inicio):
    return tuple(PalavraSTT(t, inicio + i * 400, inicio + i * 400 + 350, 0.9) for i, t in enumerate(toks))


def _legenda(pid, nome, texto, ini, fim, i):
    return {"kind": "caption", "caption_id": f"rtc-{i}/{pid}", "caption_revision": 1, "participant_id": pid,
            "display_name": nome, "text": texto, "event_id": f"e{i}", "ts_sec": ini, "ts_fim_sec": fim}


def _reuniao():
    """Você (mic) fala por cima do Bruno (loopback) no mesmo intervalo."""
    mic = SegmentoSTT("microphone-0-0", 0, 1550, AudioSource.MICROPHONE, "bafo cedi lame nipo", False,
                      _palavras("bafo cedi lame nipo".split(), 0))
    lb = SegmentoSTT("loopback-0-0", 200, 1750, AudioSource.LOOPBACK, "ruza tevi zoba gula", False,
                     _palavras("ruza tevi zoba gula".split(), 200))
    eventos = [
        _legenda("dev-88", "Alessandro", "bafo cedi lame nipo", 1.0, 2.55, 0),
        _legenda("dev-2", "Bruno", "ruza tevi zoba gula", 1.2, 2.75, 1),
        {"kind": "self_device", "participant_id": "dev-88"},
    ]
    return [mic, lb], eventos


def test_mic_herda_participante_proprio():
    segmentos, eventos = _reuniao()
    r = alinhar_segmentos(segmentos, eventos, incerteza_ms=10, proprio="dev-88")
    atr = r.atribuicoes["microphone-0-0"]
    assert atr.participant_id == "dev-88" and atr.source == "meet_proprio"


def test_rotulo_voce_com_nome_meet():
    segmentos, eventos = _reuniao()
    r = alinhar_segmentos(segmentos, eventos, incerteza_ms=10, proprio="dev-88")
    assert r.atribuicoes["microphone-0-0"].display_name == "Alessandro (você)"


def test_proprio_nunca_atribuido_a_outro():
    """O loopback não contém a voz do usuário: a legenda dele não nomeia o que veio de lá."""
    segmentos, eventos = _reuniao()
    r = alinhar_segmentos(segmentos, eventos, incerteza_ms=10, proprio="dev-88")
    lb = [s for s in r.fundidos if s.source == AudioSource.LOOPBACK]
    assert lb and all(r.atribuicoes[s.segment_id].participant_id == "dev-2" for s in lb)
    assert all(r.atribuicoes[s.segment_id].display_name == "Bruno" for s in lb)


def test_sem_nome_proprio_usa_rotulo_do_usuario():
    segmentos, eventos = _reuniao()
    eventos[0]["display_name"] = ""
    r = alinhar_segmentos(segmentos, eventos, incerteza_ms=10, proprio="dev-88", rotulo_usuario="VOCÊ")
    assert r.atribuicoes["microphone-0-0"].display_name == "VOCÊ"


def test_sem_proprio_comportamento_anterior():
    segmentos, eventos = _reuniao()
    r = alinhar_segmentos(segmentos, eventos[:2], incerteza_ms=10)
    assert r.atribuicoes["microphone-0-0"].source == "meet_alinhamento"


def test_aceite_usuario_e_duas_pessoas():
    """Aceite: todas as falas do mic saem "Alessandro (você)"; as do loopback, dos outros."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    from test_alinhador_falas import NOMES, reuniao_sintetica

    segmentos, eventos, verdade = reuniao_sintetica(21, 5)
    # dev-1 passa a ser o próprio usuário: as falas dele vão para o mic.
    NOMES_LOCAL = {**NOMES, "dev-1": "Alessandro"}
    for ev in eventos:
        ev["display_name"] = NOMES_LOCAL[ev["participant_id"]]
    eventos.append({"kind": "self_device", "participant_id": "dev-1"})
    palavras = [p for s in segmentos for p in s.words]
    mic, lb = [], []
    for p, dono in zip(palavras, verdade):
        (mic if dono == "dev-1" else lb).append(p)
    fundidos = [SegmentoSTT(f"microphone-0-{i}", p.ini_ms, p.fim_ms, AudioSource.MICROPHONE, p.w, False, (p,))
                for i, p in enumerate(mic)]
    fundidos += [SegmentoSTT(f"loopback-0-{i}", p.ini_ms, p.fim_ms, AudioSource.LOOPBACK, p.w, False, (p,))
                 for i, p in enumerate(lb)]
    r = alinhar_segmentos(fundidos, eventos, incerteza_ms=10, proprio="dev-1")
    rotulos_mic = {r.atribuicoes[s.segment_id].display_name for s in r.fundidos if s.source == AudioSource.MICROPHONE}
    assert rotulos_mic == {"Alessandro (você)"}
    assert not any(r.atribuicoes[s.segment_id].participant_id == "dev-1"
                   for s in r.fundidos if s.source == AudioSource.LOOPBACK)


def test_retranscritor_passa_o_dispositivo_proprio(monkeypatch):
    """O worker entrega o self_device e o rótulo do usuário ao alinhador."""
    import alinhador_falas
    import retranscritor

    visto = {}

    def espiao(fundidos, eventos, **kwargs):
        visto.update(kwargs)
        return alinhador_falas.ResultadoAlinhamento(list(fundidos), {}, None)

    monkeypatch.setattr(alinhador_falas, "alinhar_segmentos", espiao)
    monkeypatch.setattr(retranscritor, "_carregar_modelo", lambda *a, **k: object())
    monkeypatch.setattr("audio_fontes.transcrever_fonte", lambda *a, **k: [])
    monkeypatch.setattr("audio_reader.inspect_audio", lambda *a, **k: type("I", (), {"total_frames": 16000, "sample_rate": 16000})())
    import tempfile

    with tempfile.TemporaryDirectory() as pasta:
        retranscritor.retranscrever_resultado(
            "audio.wav", pasta_saida=pasta, nome_base_saida="reuniao_b2", diarizar=False,
            eventos_meet=[{"kind": "self_device", "participant_id": "dev-88"}], rotulo_usuario="VOCÊ",
        )
    assert visto["proprio"] == "dev-88" and visto["rotulo_usuario"] == "VOCÊ"


def test_fala_propria_sobreposta_nao_captura_o_loopback():
    """Sua legenda cobre o trecho inteiro; a do Bruno, só parte, e sem âncora de texto.

    Sem excluir o próprio dispositivo do loopback, as palavras do Bruno fora
    da legenda dele iriam para você — a voz que o loopback nunca contém.
    """
    lb = SegmentoSTT("loopback-0-0", 200, 1750, AudioSource.LOOPBACK, "ruza tevi zoba gula", False,
                     _palavras("ruza tevi zoba gula".split(), 200))
    eventos = [
        _legenda("dev-88", "Alessandro", "outra coisa dita", 1.0, 4.0, 0),
        _legenda("dev-2", "Bruno", "xxxx yyyy", 2.0, 2.6, 1),
        {"kind": "self_device", "participant_id": "dev-88"},
    ]
    r = alinhar_segmentos([lb], eventos, incerteza_ms=10, proprio="dev-88")
    assert {r.atribuicoes[s.segment_id].participant_id for s in r.fundidos} == {"dev-2"}
