# -*- coding: utf-8 -*-
"""FR-10.D3/D4 e FR-10.E — pós-processamento isolado e texto legível."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

import retranscritor
from crypto_storage import ler_transcricao
from fila_processamento import FilaProcessamento
from processador_reuniao import flags_subprocesso_windows, processar_job


class _Seg:
    def __init__(self, text, start, end):
        self.text = text
        self.start = start
        self.end = end


@pytest.fixture
def fila_com_job(tmp_path):
    pasta = tmp_path / "transcricoes"
    audio_dir = pasta / "audio"
    audio_dir.mkdir(parents=True)
    audio = audio_dir / "reuniao_audio.wav"
    dados = (np.sin(2 * np.pi * 220 * np.arange(8000) / 16000) * 0.2 * 32767).astype(
        np.int16
    )
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(dados.tobytes())
    fila = FilaProcessamento(str(pasta))
    job_id = fila.enfileirar(
        str(audio),
        None,
        "reuniao_2026-08-06_09h31",
        {
            "origem": "meet",
            "inicio_iso": "2026-08-06T09:31:13-03:00",
            "fim_iso": "2026-08-06T09:31:13.500000-03:00",
            "duracao_seg": 0.5,
            "diarizar": False,
            "criptografar": True,
        },
    )
    return fila, job_id, audio


@pytest.fixture
def modelo_fake():
    modelo = MagicMock()
    modelo.transcribe.return_value = (
        [_Seg("decisão importante da reunião", 0.0, 0.4)],
        MagicMock(),
    )
    return modelo


def test_processador_cria_txt_utf8_e_copia_tkpt(
    chave_teste, fila_com_job, modelo_fake
):
    fila, job_id, _audio = fila_com_job

    resultado = processar_job(job_id, modelo_whisper=modelo_fake, fila=fila)

    assert resultado.suffix == ".txt"
    texto = resultado.read_text(encoding="utf-8")
    assert texto.startswith("=== Transcricao")
    assert "[00:00:00]" in texto
    assert "decisão importante" in texto
    copia = resultado.with_suffix(".tkpt")
    assert copia.is_file()
    assert ler_transcricao(copia.name, str(copia.parent)) == texto
    assert fila.obter(job_id).estado == "ready"


def test_falha_mantem_audio_e_marca_job(fila_com_job, monkeypatch):
    fila, job_id, audio = fila_com_job

    def falhar(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(retranscritor, "retranscrever", falhar)
    with pytest.raises(RuntimeError):
        processar_job(job_id, fila=fila)

    assert audio.is_file()
    job = fila.obter(job_id)
    assert job.estado == "failed"
    assert job.erro_seguro == "runtimeerror"


def test_flags_windows_sao_sem_janela_e_prioridade_baixa():
    flags = flags_subprocesso_windows()
    assert flags & subprocess.CREATE_NO_WINDOW
    assert flags & subprocess.BELOW_NORMAL_PRIORITY_CLASS
