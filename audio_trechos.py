# -*- coding: utf-8 -*-
"""Extrai trechos de fonte cifrada em um passe, sem WAV temporário."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from audio_reader import AudioSource, inspect_audio, iter_audio_16k
from config import SAMPLE_RATE


def extrair_trechos(path: Path, fonte: AudioSource,
                    intervalos: Sequence[tuple[float, float, str]]) -> list[np.ndarray]:
    info = inspect_audio(path, fonte)
    partes: list[list[np.ndarray]] = [[] for _ in intervalos]
    limites = [(max(0, int(inicio * SAMPLE_RATE)),
                max(0, int(fim * SAMPLE_RATE))) for inicio, fim, _texto in intervalos]
    for bloco in iter_audio_16k(path, fonte):
        inicio_bloco = round(bloco.start_frame * SAMPLE_RATE / info.sample_rate)
        fim_bloco = inicio_bloco + bloco.samples.size
        for indice, (inicio, fim) in enumerate(limites):
            a, b = max(inicio, inicio_bloco), min(fim, fim_bloco)
            if a < b:
                partes[indice].append(bloco.samples[a - inicio_bloco:b - inicio_bloco].copy())
    return [np.concatenate(p) if p else np.array([], dtype=np.float32) for p in partes]


def selecionar_trechos_por_fonte(
    origens: Sequence[AudioSource | str],
    loopback: Sequence[np.ndarray],
    microphone: Sequence[np.ndarray] | None,
) -> list[np.ndarray]:
    """Entrega ao diarizador o áudio da fonte real de cada segmento STT."""
    if len(origens) != len(loopback) or (microphone is not None and len(origens) != len(microphone)):
        raise ValueError("trechos de áudio não correspondem aos segmentos")
    selecionados = []
    for i, origem in enumerate(origens):
        fonte = origem.value if isinstance(origem, AudioSource) else origem
        if fonte == AudioSource.MICROPHONE.value:
            if microphone is None:
                raise ValueError("segmento de microfone sem áudio de microfone")
            selecionados.append(microphone[i])
        elif fonte == AudioSource.LOOPBACK.value:
            selecionados.append(loopback[i])
        else:
            raise ValueError("origem de áudio desconhecida")
    return selecionados
