# -*- coding: utf-8 -*-
"""Utilitários de áudio compartilhados (FR-5.5)."""
from __future__ import annotations

import os
import wave

import numpy as np

from config import SAMPLE_RATE


def ler_trecho_wav(caminho_wav, start_sec, end_sec, sample_rate=SAMPLE_RATE):
    """Lê um trecho do WAV em float32 normalizado (não carrega o arquivo inteiro).

    Usado por diarizador e transcricao_core — única implementação (FR-5.5).
    """
    if not caminho_wav or not os.path.isfile(caminho_wav):
        return np.array([], dtype=np.float32)
    w = wave.open(caminho_wav, "rb")
    try:
        total = w.getnframes()
        i_start = max(0, int(start_sec * sample_rate))
        i_end = min(total, int(end_sec * sample_rate))
        if i_start >= i_end:
            return np.array([], dtype=np.float32)
        w.setpos(i_start)
        frames = w.readframes(i_end - i_start)
        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
    finally:
        w.close()
