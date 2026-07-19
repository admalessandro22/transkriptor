# -*- coding: utf-8 -*-
"""Testes de audio_utils.ler_trecho_wav (FR-5.5)."""
import wave

import numpy as np
import pytest

from audio_utils import ler_trecho_wav


def _escrever_wav(caminho, samples: np.ndarray, sr: int = 16000) -> None:
    dados = (samples.astype(np.float32) * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(dados.tobytes())


def test_ler_trecho_wav_recorte_completo(tmp_path):
    """FR-5.5: lê trecho interno com sample_rate configurável."""
    sr = 16000
    # 2s: 0..1s = 0.5, 1..2s = -0.5
    a = np.ones(sr, dtype=np.float32) * 0.5
    b = np.ones(sr, dtype=np.float32) * -0.5
    samples = np.concatenate([a, b])
    caminho = tmp_path / "t.wav"
    _escrever_wav(caminho, samples, sr)

    trecho = ler_trecho_wav(str(caminho), 1.0, 2.0, sample_rate=sr)
    assert trecho.size == sr
    assert float(np.mean(trecho)) == pytest.approx(-0.5, abs=0.02)


def test_ler_trecho_wav_limites_inicio_fim(tmp_path):
    """FR-5.5: start negativo e end além do arquivo são clampeados."""
    sr = 8000
    samples = np.linspace(-0.3, 0.3, sr * 2, dtype=np.float32)
    caminho = tmp_path / "lim.wav"
    _escrever_wav(caminho, samples, sr)

    trecho = ler_trecho_wav(str(caminho), -1.0, 99.0, sample_rate=sr)
    assert trecho.size == samples.size
    assert float(trecho[0]) == pytest.approx(samples[0], abs=0.02)


def test_ler_trecho_wav_start_maior_que_end_retorna_vazio(tmp_path):
    sr = 16000
    caminho = tmp_path / "vazio.wav"
    _escrever_wav(caminho, np.ones(sr, dtype=np.float32) * 0.1, sr)
    trecho = ler_trecho_wav(str(caminho), 0.8, 0.2, sample_rate=sr)
    assert trecho.size == 0
    assert trecho.dtype == np.float32


def test_ler_trecho_wav_inexistente_retorna_vazio():
    """FR-5.5: caminho inexistente ou vazio não lança."""
    vazio = ler_trecho_wav(None, 0.0, 1.0)
    assert vazio.size == 0
    assert vazio.dtype == np.float32
    vazio2 = ler_trecho_wav("C:/caminho/que/nao/existe.wav", 0.0, 1.0)
    assert vazio2.size == 0
