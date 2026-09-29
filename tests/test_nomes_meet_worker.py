# -*- coding: utf-8 -*-
"""T-13.D5 — eventos da sessão atravessam job v2 até o worker (Ana/Bruno sintéticos)."""
from __future__ import annotations

import json
import time
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from fila_processamento import FilaProcessamento

CONSENTIDA = "2026-09-19T20:00:00Z"
WALL_BASE = 1_789_848_060_000


class _Seg:
    def __init__(self, text, start, end):
        self.text = text
        self.start = start
        self.end = end


def _escrever_wav(path: Path, segundos=1.0, sr=16000):
    n = int(segundos * sr)
    audio = (np.sin(2 * np.pi * 440 * np.arange(n) / sr) * 0.2 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())
    return path


def _sessao_snapshot(session_id="sess-d5", meeting="reuniao-d5"):
    return {
        "session_id": session_id,
        "meeting_key": meeting,
        "consented_at_utc": CONSENTIDA,
        "policy_id": "padrao",
        "first_frame_monotonic_ns": 111_000_000_000,
        "offset_ms": 20.0,
        "relogio_incerto": False,
    }


def _evento(sessao_id, meeting, seq, nome, texto):
    return {
        "schema_version": 1,
        "event_id": f"e-{seq}",
        "session_id": sessao_id,
        "connection_id": "c1",
        "seq": seq,
        "tab_id": "aba-1",
        "meeting_key": meeting,
        "kind": "caption",
        "client_wall_ms": WALL_BASE + seq * 1000,
        "client_monotonic_ms": 1000 + seq,
        "received_monotonic_ns": time.monotonic_ns(),
        "display_name": nome,
        "text": texto,
    }


def _job_com_eventos(pasta, chave_teste, audio):
    """Sela Ana+Bruno no store e enfileira job v2; devolve (fila, job_id, espionado)."""
    import dataclasses

    from eventos_meet_store import EventStore
    from sessao_reuniao import criar_sessao

    sessao = criar_sessao("reuniao-d5", CONSENTIDA, "padrao")
    store = EventStore(pasta / "tr" / "eventos_privados", sessao, ancora_refs=pasta / "tr")
    store.append(_evento(sessao.session_id, "reuniao-d5", 0, "Ana", "bom dia a todos"))
    store.append(_evento(sessao.session_id, "reuniao-d5", 1, "Bruno", "vamos revisar o cronograma"))
    refs = store.seal()
    assert len(refs) >= 1
    fila = FilaProcessamento(str(pasta / "tr"))
    snapshot = _sessao_snapshot(sessao.session_id, "reuniao-d5")
    job_id = fila.enfileirar(
        str(audio),
        None,
        "reuniao-d5",
        {"origem": "gate", "diarizar": True, "idioma": "pt"},
        sessao=snapshot,
        eventos_refs=[dataclasses.asdict(r) for r in refs],
        preferencias={"rotulo_usuario": "VOCÊ", "usar_vozes_conhecidas": False},
    )
    return fila, job_id


def _modelo_duas_falas():
    modelo = MagicMock()
    modelo.transcribe.return_value = (
        [
            _Seg("bom dia a todos", 0.0, 0.4),
            _Seg("vamos revisar o cronograma", 0.4, 0.9),
        ],
        MagicMock(),
    )
    return modelo


def _espiao_diarizar():
    visto = {}

    def _fake(trechos, segmentos, **kwargs):
        visto["eventos_meet"] = list(kwargs.get("eventos_meet") or [])
        visto["rotulo"] = kwargs.get("rotulo_usuario")
        resultado = [("FALANTE_00", s, e, t) for s, e, t in segmentos]
        if kwargs.get("retornar_centroides"):
            return resultado, {}
        return resultado

    return visto, _fake


def test_nome_atravessa_job_e_worker_novo(chave_teste, tmp_path):
    """Eventos Ana/Bruno chegam à diarização via refs do job (nome no segmento)."""
    from processador_reuniao import processar_job

    pasta = tmp_path
    (pasta / "tr").mkdir()
    audio = _escrever_wav(pasta / "tr" / "audio.wav")
    fila, job_id = _job_com_eventos(pasta, chave_teste, audio)
    assert fila.obter(job_id).eventos_refs, "job v2 leva refs de eventos"

    visto, fake = _espiao_diarizar()
    with patch("diarizador.diarizar", side_effect=fake):
        resultado = processar_job(job_id, modelo_whisper=_modelo_duas_falas(), fila=fila)
    nomes = " ".join(e.get("display_name", "") for e in visto["eventos_meet"])
    assert "Ana" in nomes and "Bruno" in nomes
    texto = Path(resultado).read_text(encoding="utf-8").lower()
    assert "bom dia" in texto and "cronograma" in texto
    from resultado_reuniao import carregar_manifesto, carregar_segmentos

    manifesto = carregar_manifesto(Path(fila.obter(job_id).manifesto_resultado))
    dados = carregar_segmentos(fila.pasta_transcricoes / manifesto.segments_ref.relative_path)
    assert dados["segmentos"][0]["assignment"]["status"] == "suggested"
    assert "Ana" not in texto


def test_restart_preserva_eventos(chave_teste, tmp_path):
    """Job pendente sobrevive a restart (nova Fila) com refs intactas."""
    from processador_reuniao import processar_job

    pasta = tmp_path
    (pasta / "tr").mkdir()
    audio = _escrever_wav(pasta / "tr" / "audio.wav")
    fila, job_id = _job_com_eventos(pasta, chave_teste, audio)
    del fila
    fila2 = FilaProcessamento(str(pasta / "tr"))
    job = fila2.obter(job_id)
    assert job.estado == "pending" and len(job.eventos_refs) >= 1
    visto, fake = _espiao_diarizar()
    with patch("diarizador.diarizar", side_effect=fake):
        processar_job(job_id, modelo_whisper=_modelo_duas_falas(), fila=fila2)
    assert fila2.obter(job_id).estado == "ready"
    assert any(e.get("display_name") == "Ana" for e in visto["eventos_meet"])


def test_hash_incorreto_recusa_eventos(chave_teste, tmp_path):
    """Artefato adulterado não entra: worker avisa e segue sem nomes."""
    from processador_reuniao import processar_job

    pasta = tmp_path
    (pasta / "tr").mkdir()
    audio = _escrever_wav(pasta / "tr" / "audio.wav")
    fila, job_id = _job_com_eventos(pasta, chave_teste, audio)
    ref = fila.obter(job_id).eventos_refs[0]
    alvo = pasta / "tr" / ref["relative_path"]
    with open(alvo, "r+b") as f:
        f.seek(0, 2)
        f.write(b"\x00" * 16)
    visto, fake = _espiao_diarizar()
    with patch("diarizador.diarizar", side_effect=fake):
        processar_job(job_id, modelo_whisper=_modelo_duas_falas(), fila=fila)
    job = fila.obter(job_id)
    assert job.estado == "ready"
    assert visto["eventos_meet"] == []
    assert any("evento" in w for w in job.warnings)


def test_job_v1_sem_nome_nao_fabrica_participante(chave_teste, tmp_path):
    """Job v1 (sem sessão/refs) resulta em FALANTE, nunca nome inventado."""
    from processador_reuniao import processar_job

    pasta = tmp_path
    (pasta / "tr").mkdir()
    audio = _escrever_wav(pasta / "tr" / "audio.wav")
    fila = FilaProcessamento(str(pasta / "tr"))
    job_id = fila.enfileirar(
        str(audio), None, "reuniao-v1", {"origem": "gate", "diarizar": True, "idioma": "pt"}
    )
    visto, fake = _espiao_diarizar()
    with patch("diarizador.diarizar", side_effect=fake):
        resultado = processar_job(job_id, modelo_whisper=_modelo_duas_falas(), fila=fila)
    assert visto["eventos_meet"] == []
    assert "Ana" not in Path(resultado).read_text(encoding="utf-8")


def test_fala_com_relogio_chega_no_tempo_do_audio(chave_teste, tmp_path):
    """T-15.A2: evento carimbado pela ponte vira ts_sec relativo ao 1º frame."""
    import dataclasses

    from eventos_meet_store import EventStore
    from processador_reuniao import processar_job
    from sessao_reuniao import criar_sessao

    (tmp_path / "tr").mkdir()
    audio = _escrever_wav(tmp_path / "tr" / "audio.wav")
    sessao = criar_sessao("reuniao-a2", CONSENTIDA, "padrao")
    store = EventStore(tmp_path / "tr" / "eventos_privados", sessao, ancora_refs=tmp_path / "tr")
    ev = _evento(sessao.session_id, "reuniao-a2", 0, "Ana", "bom dia a todos")
    primeiro_frame = 111_000_000_000
    ev.update({"speech_started_monotonic_ns": primeiro_frame + 250_000_000,
               "speech_last_monotonic_ns": primeiro_frame + 400_000_000,
               "clock_uncertainty_ms": 6.0})
    store.append(ev)
    refs = store.seal()
    fila = FilaProcessamento(str(tmp_path / "tr"))
    snapshot = _sessao_snapshot(sessao.session_id, "reuniao-a2")
    snapshot["relogio_incerto"] = True  # o snapshot antigo não decide mais
    job_id = fila.enfileirar(
        str(audio), None, "reuniao-a2", {"origem": "gate", "diarizar": True, "idioma": "pt"},
        sessao=snapshot, eventos_refs=[dataclasses.asdict(r) for r in refs],
        preferencias={"rotulo_usuario": "VOCÊ", "usar_vozes_conhecidas": False},
    )
    visto, fake = _espiao_diarizar()
    capturado = {}
    import identidade_reuniao

    original = identidade_reuniao.resolver_atribuicao

    def _espiao_resolver(*args, **kwargs):
        capturado["incerteza"] = kwargs.get("clock_uncertainty_ms")
        return original(*args, **kwargs)

    with patch("diarizador.diarizar", side_effect=fake), \
            patch("identidade_reuniao.resolver_atribuicao", side_effect=_espiao_resolver):
        processar_job(job_id, modelo_whisper=_modelo_duas_falas(), fila=fila)
    eventos = visto["eventos_meet"]
    assert eventos[0]["ts_sec"] == 0.25
    assert capturado.get("incerteza") == 6


def test_aviso_sem_nomes_le_event_store(chave_teste, tmp_path):
    """G-14: com a ponte pareada a fila legada fica vazia; o aviso consulta o store."""
    from app_ciclo_reuniao import CicloReuniaoMixin
    from eventos_meet_store import EventStore
    from sessao_reuniao import criar_sessao

    sessao = criar_sessao("reuniao-g14", CONSENTIDA, "padrao")
    store = EventStore(tmp_path / "eventos", sessao)
    ciclo = CicloReuniaoMixin()
    ciclo.modo_legendas_meet = True
    ciclo._eventos_store = store
    assert ciclo._sem_nomes_do_meet([]) is True
    store.append(_evento(sessao.session_id, "reuniao-g14", 0, "Ana", "bom dia"))
    assert ciclo._sem_nomes_do_meet([]) is False
    ciclo._eventos_store = None
    assert ciclo._sem_nomes_do_meet([{"nome": "Ana"}]) is False
    ciclo.modo_legendas_meet = False
    assert ciclo._sem_nomes_do_meet([]) is False
