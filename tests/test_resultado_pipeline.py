# -*- coding: utf-8 -*-
"""O worker entrega o JSON canônico antes de concluir a fila."""
from __future__ import annotations

import wave
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from audio_fontes import SegmentoSTT
from audio_reader import AudioSource
from artefatos import criar_referencia
from fila_processamento import FilaProcessamento
from processador_reuniao import processar_job
from resultado_pipeline import criar_segmentos
from resultado_reuniao import (
    StageState, carregar_manifesto, carregar_segmentos, salvar_manifesto, validar_manifesto,
)


def test_worker_materializa_resultado_estruturado(tmp_path, chave_teste):
    raiz = tmp_path / "transcricoes"
    pasta_audio = raiz / "audio"
    pasta_audio.mkdir(parents=True)
    audio = pasta_audio / "reuniao.wav"
    with wave.open(str(audio), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(16000)
        arquivo.writeframes(np.zeros(8000, dtype=np.int16).tobytes())
    fila = FilaProcessamento(str(raiz))
    job_id = fila.enfileirar(str(audio), None, "reuniao", {"origem": "meet", "diarizar": False})
    modelo = MagicMock()
    modelo.transcribe.return_value = ([SimpleNamespace(text="decisão da reunião", start=0, end=0.4)], MagicMock())

    processar_job(job_id, modelo_whisper=modelo, fila=fila)

    job = fila.obter(job_id)
    manifesto = carregar_manifesto(Path(job.manifesto_resultado))
    assert manifesto.segments_ref.relative_path == f"resultados/{job_id}.json"
    dados = carregar_segmentos(raiz / manifesto.segments_ref.relative_path)
    assert dados["segmentos"][0]["segment_id"]
    assert dados["segmentos"][0]["audio_source"] == "loopback"
    assert manifesto.stage_status["stt"] is StageState.COMPLETE
    assert manifesto.stage_status["diarizacao"] is StageState.SKIPPED
    antes = (raiz / "reuniao.txt").read_bytes()
    novo_job = fila.enfileirar(str(audio), None, "reuniao", {"origem": "meet", "diarizar": False})
    with pytest.raises(FileExistsError):
        processar_job(novo_job, modelo_whisper=modelo, fila=fila)
    assert fila.obter(novo_job).estado == "failed"
    assert (raiz / "reuniao.txt").read_bytes() == antes
    assert audio.is_file()


def test_alinhamento_nao_transfere_rotulo_por_indice():
    fundidos = (
        SegmentoSTT("lb-1", 0, 400, AudioSource.LOOPBACK, "primeira", False),
        SegmentoSTT("mic-1", 400, 900, AudioSource.MICROPHONE, "segunda", False),
    )
    diarizados = (("FALANTE_01", 0.4, 0.9, "segunda"), ("FALANTE_02", 0, 0.4, "primeira"))
    segmentos, warnings = criar_segmentos(fundidos, diarizados)
    assert [s.speaker_cluster_id for s in segmentos] == ["FALANTE_02", "FALANTE_01"]
    assert [s.audio_source for s in segmentos] == ["loopback", "microphone"]
    assert warnings == ()

    segmentos, warnings = criar_segmentos(fundidos, diarizados[:1])
    assert segmentos[0].speaker_cluster_id == "FALANTE_00"
    assert warnings == ("segment_alignment_failed",)


def test_manifesto_com_json_malformado_nao_libera_retencao(tmp_path):
    raiz = tmp_path
    audio = raiz / "audio.wav"
    audio.write_bytes(b"RIFF")
    segmentos = raiz / "resultados" / "reuniao.json"
    segmentos.parent.mkdir()
    segmentos.write_text('{"schema_version": 1, "revision": "rev-1", "segmentos": [], "mapeamento": {}}', encoding="utf-8")
    txt = raiz / "reuniao.txt"
    txt.write_text("[00:00:00] Identificação pendente: fala\n", encoding="utf-8")
    from resultado_reuniao import criar_manifesto_estruturado

    manifesto = criar_manifesto_estruturado(
        meeting_id="reuniao", segmentos=segmentos, resultado=txt,
        fontes_audio=[audio], raiz=raiz,
    )
    segmentos.write_text('{"schema_version": 1, "revision": "rev-1", "segmentos": [{"text":"fala"}], "mapeamento": {}}', encoding="utf-8")
    manifesto = replace(manifesto, segments_ref=criar_referencia(
        segmentos, raiz, format="application/vnd.transkriptor.segments+json", schema_version=1,
    ))
    caminho = raiz / "reuniao.resultado.json"
    salvar_manifesto(caminho, manifesto)
    assert validar_manifesto(caminho, raiz) is False
