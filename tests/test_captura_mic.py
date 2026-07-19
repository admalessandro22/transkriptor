# -*- coding: utf-8 -*-
"""Testes de captura paralela do microfone (Fase 7 — FR-7.5)."""
import os
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np

from transcricao_core import Transcritor


class _RecorderMock:
    def __init__(self, samplerate, channels):
        self.samplerate = samplerate
        self.channels = channels
        self.frames = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def record(self, numframes):
        self.frames += numframes
        return np.zeros((numframes, 1), dtype=np.float32)


def test_abrir_arquivo_cria_mic_wav_quando_habilitado(tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), diarizar_ao_final=True, capturar_mic=True)
    t._abrir_arquivo()
    assert t._caminho_wav_mic is not None
    assert t._caminho_wav_mic.endswith("_mic.wav")
    assert t._wav_mic is not None
    t._wav_mic.close()


def test_abrir_arquivo_sem_mic_nao_cria_wav_mic(tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), diarizar_ao_final=True, capturar_mic=False)
    t._abrir_arquivo()
    assert t._caminho_wav_mic is None
    assert t._wav_mic is None


def test_stop_fecha_mic_apos_thread_mic(tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), diarizar_ao_final=False, capturar_mic=True)
    t._stop = threading.Event()
    t._abrir_arquivo()
    mic_mock = MagicMock()
    mic_mock.recorder.return_value = _RecorderMock(16000, 1)
    with patch("transcricao_core.sc.default_microphone", return_value=mic_mock):
        t.rodando = True
        t._thread_mic = threading.Thread(target=t._capturar_mic, daemon=True)
        t._thread_mic.start()
        time.sleep(0.1)
        t.stop()
    assert t._wav_mic is None
    assert os.path.isfile(t._caminho_wav_mic)


def test_stop_encerra_thread_mic(tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), diarizar_ao_final=False, capturar_mic=True)
    t._stop = threading.Event()
    t._abrir_arquivo()

    mic_mock = MagicMock()
    mic_mock.recorder.return_value = _RecorderMock(16000, 1)

    with patch("transcricao_core.sc.default_microphone", return_value=mic_mock):
        t._thread_mic = threading.Thread(target=t._capturar_mic, daemon=True)
        t._thread_mic.start()
        time.sleep(0.15)
        t._stop.set()
        t._thread_mic.join(timeout=2)

    assert not t._thread_mic.is_alive()
    if t._wav_mic:
        t._wav_mic.close()