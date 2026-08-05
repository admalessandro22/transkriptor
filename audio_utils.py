# -*- coding: utf-8 -*-
"""Utilitários de áudio compartilhados (FR-5.5) e autoteste de captura (FR-9.5)."""
from __future__ import annotations

import logging
import os
import wave

import numpy as np

from config import SAMPLE_RATE

logger = logging.getLogger(__name__)


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


def diagnosticar_captura(bloco, erro=None):
    """FR-9.5: classifica o resultado de uma tentativa de captura.

    Função pura — o teste cobre os casos sem depender de placa de som.

    Retorna dict `{ok, motivo, rms, frames}`. `ok=False` significa que a
    gravação produziria um arquivo vazio: precisa virar aviso para o usuário,
    nunca um erro silencioso engolido pelo loop de captura.
    """
    if erro is not None:
        return {"ok": False, "motivo": f"falha na captura: {erro}", "rms": 0.0, "frames": 0}
    if bloco is None or getattr(bloco, "size", 0) == 0:
        return {"ok": False, "motivo": "nenhum quadro de áudio recebido", "rms": 0.0, "frames": 0}
    dados = np.asarray(bloco, dtype=np.float32)
    rms = float(np.sqrt(np.mean(np.square(dados)))) if dados.size else 0.0
    return {"ok": True, "motivo": "captura funcional", "rms": rms, "frames": int(dados.size)}


def testar_loopback(segundos=0.5, sample_rate=SAMPLE_RATE):
    """Abre o loopback do alto-falante padrão e grava um bloco curto.

    Usado no autoteste de inicialização e no diagnóstico da bandeja. Nunca
    levanta: devolve o dict de `diagnosticar_captura` com `dispositivo`.
    """
    dispositivo = ""
    try:
        import soundcard as sc

        alto_falante = sc.default_speaker()
        dispositivo = str(getattr(alto_falante, "name", "") or "")
        loop_id = getattr(alto_falante, "id", None) or dispositivo
        mic = sc.get_microphone(id=str(loop_id), include_loopback=True)
        with mic.recorder(samplerate=sample_rate, channels=1) as rec:
            bloco = rec.record(numframes=int(sample_rate * segundos))
    except Exception as e:  # noqa: BLE001 — o diagnóstico precisa do motivo
        logger.warning("Autoteste de loopback falhou: %s", e)
        resultado = diagnosticar_captura(None, erro=e)
        resultado["dispositivo"] = dispositivo
        return resultado
    resultado = diagnosticar_captura(bloco)
    resultado["dispositivo"] = dispositivo
    return resultado


def testar_microfone(segundos=0.5, sample_rate=SAMPLE_RATE):
    """Mesmo autoteste de `testar_loopback`, para o microfone padrão."""
    dispositivo = ""
    try:
        import soundcard as sc

        mic = sc.default_microphone()
        dispositivo = str(getattr(mic, "name", "") or "")
        with mic.recorder(samplerate=sample_rate, channels=1) as rec:
            bloco = rec.record(numframes=int(sample_rate * segundos))
    except Exception as e:  # noqa: BLE001
        logger.warning("Autoteste de microfone falhou: %s", e)
        resultado = diagnosticar_captura(None, erro=e)
        resultado["dispositivo"] = dispositivo
        return resultado
    resultado = diagnosticar_captura(bloco)
    resultado["dispositivo"] = dispositivo
    return resultado
