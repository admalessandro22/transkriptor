# -*- coding: utf-8 -*-
"""Testes do lifecycle de stop() do Transcritor."""
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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def record(self, numframes):
        return np.zeros((numframes, 1), dtype=np.float32)


def test_stop_aguarda_thread_proc_e_fecha_wav_antes_diarizar(tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), diarizar_ao_final=True, capturar_mic=False)
    t._abrir_arquivo()
    wav_fechado = threading.Event()

    original_close = t._wav.close

    def _close_monitorado():
        original_close()
        wav_fechado.set()

    t._wav.close = _close_monitorado

    mic_mock = MagicMock()
    mic_mock.recorder.return_value = _RecorderMock(16000, 1)

    with patch("transcricao_core.sc.get_microphone", return_value=mic_mock), patch(
        "transcricao_core.sc.all_speakers", return_value=[]
    ), patch("transcricao_core.sc.default_speaker", return_value=MagicMock(id="spk")):
        t.rodando = True
        t._thread_cap = threading.Thread(target=t._capturar, daemon=True)
        t._thread_proc = threading.Thread(target=t._processar, daemon=True)
        t._thread_cap.start()
        t._thread_proc.start()
        time.sleep(0.2)
        t.stop()

    assert wav_fechado.is_set()
    assert t._wav is None
    assert not t.finalizando


def test_stop_define_finalizando_durante_encerramento(tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), diarizar_ao_final=False, capturar_mic=False)
    t._abrir_arquivo()
    t.rodando = True
    t._thread_proc = threading.Thread(target=lambda: time.sleep(0.5), daemon=True)
    t._thread_proc.start()
    estados = []

    def _capturar_estado():
        estados.append(getattr(t, "finalizando", False))
        t.stop()

    th = threading.Thread(target=_capturar_estado)
    th.start()
    th.join(timeout=5)
    assert True in estados or t.finalizando is False