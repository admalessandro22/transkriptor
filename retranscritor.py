# -*- coding: utf-8 -*-
"""Retranscrição offline de áudios retidos (FR-2.5)."""
from __future__ import annotations

import datetime
import logging
import os
import tempfile
import wave
from pathlib import Path

import numpy as np

from config import CHUNK_SEGUNDOS, PASTA_AUDIO, PASTA_TRANSCRICOES, SAMPLE_RATE
from transcricao_core import Transcritor

logger = logging.getLogger(__name__)


def _ler_audio_pcm(caminho: str) -> tuple[np.ndarray, int]:
    """Retorna (float32 mono, sample_rate) de .wav ou .wav.enc."""
    path = Path(caminho)
    if not path.is_file():
        raise FileNotFoundError(caminho)
    tmp_wav = None
    try:
        if path.name.lower().endswith(".wav.enc"):
            from crypto_storage import ler_bytes_arquivo

            plano = ler_bytes_arquivo(str(path))
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            Path(tmp_wav).write_bytes(plano)
            wav_path = tmp_wav
        else:
            wav_path = str(path)
        with wave.open(wav_path, "rb") as w:
            sr = w.getframerate()
            nch = w.getnchannels()
            sw = w.getsampwidth()
            frames = w.readframes(w.getnframes())
        if sw == 2:
            data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
        else:
            data = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
        if nch > 1:
            data = data.reshape(-1, nch).mean(axis=1)
        return data, sr
    finally:
        if tmp_wav and os.path.isfile(tmp_wav):
            try:
                os.remove(tmp_wav)
            except OSError:
                pass


def listar_audios(pasta_audio: str | None = None) -> list[dict]:
    """Lista áudios em PASTA_AUDIO com data e duração (header WAV)."""
    pasta = Path(pasta_audio or PASTA_AUDIO)
    if not pasta.is_dir():
        return []
    items = []
    for path in sorted(pasta.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        nome = path.name.lower()
        if not (nome.endswith(".wav") or nome.endswith(".wav.enc")):
            continue
        dur = 0.0
        try:
            if nome.endswith(".wav.enc"):
                from crypto_storage import ler_bytes_arquivo

                plano = ler_bytes_arquivo(str(path))
                # header WAV: sample rate em bytes 24-28, data size em 40-44
                if len(plano) >= 44 and plano[:4] == b"RIFF":
                    sr = struct_unpack_sr(plano)
                    # data chunk size approx
                    nframes = max(0, (len(plano) - 44) // 2)
                    dur = nframes / float(sr or SAMPLE_RATE)
            else:
                with wave.open(str(path), "rb") as w:
                    dur = w.getnframes() / float(w.getframerate() or SAMPLE_RATE)
        except Exception:
            logger.debug("Não foi possível ler duração de %s", path.name, exc_info=True)
        mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
        items.append(
            {
                "caminho": str(path),
                "nome": path.name,
                "duracao_seg": dur,
                "mtime": mtime,
                "rotulo": f"{mtime:%d/%m/%Y %H:%M} — {dur:.0f}s — {path.name}",
            }
        )
    return items


def struct_unpack_sr(plano: bytes) -> int:
    import struct

    return struct.unpack_from("<I", plano, 24)[0]


def retranscrever(
    caminho_audio: str,
    *,
    pasta_saida: str | None = None,
    modelo_whisper=None,
    diarizar: bool = True,
    chunk: float = CHUNK_SEGUNDOS,
    criptografar: bool | None = None,
    on_status=None,
    identificar_voz: bool = False,
    usar_vozes_conhecidas: bool = True,
    **_kwargs,
) -> str:
    """Retranscreve WAV (ou .wav.enc) gerando os mesmos artefatos da reunião ao vivo."""
    on_status = on_status or (lambda _m: None)
    pasta = pasta_saida or PASTA_TRANSCRICOES
    os.makedirs(pasta, exist_ok=True)

    audio, sr = _ler_audio_pcm(caminho_audio)
    if sr != SAMPLE_RATE and audio.size:
        # reamostragem linear simples
        n_out = int(audio.size * SAMPLE_RATE / sr)
        x_old = np.linspace(0, 1, num=audio.size, endpoint=False)
        x_new = np.linspace(0, 1, num=n_out, endpoint=False)
        audio = np.interp(x_new, x_old, audio).astype(np.float32)

    t = Transcritor(
        pasta_saida=pasta,
        diarizar_ao_final=diarizar,
        capturar_mic=False,
        identificar_voz=identificar_voz,
        usar_vozes_conhecidas=usar_vozes_conhecidas,
        criptografar=criptografar,
        on_status=on_status,
        chunk=chunk,
    )
    if modelo_whisper is not None:
        t._modelo = modelo_whisper
    else:
        t._carregar_modelo()

    t._abrir_arquivo()
    # retranscrição não re-grava o áudio no WAV de captura — fecha e remove temp
    if t._wav:
        t._wav.close()
        t._wav = None
    if t._caminho_wav and os.path.isfile(t._caminho_wav):
        try:
            os.remove(t._caminho_wav)
        except OSError:
            pass
        t._caminho_wav = None

    bloco = int(SAMPLE_RATE * chunk)
    if bloco < 1:
        bloco = SAMPLE_RATE
    n = audio.size
    i = 0
    while i < n:
        fim = min(n, i + bloco)
        t._transcrever_bloco(audio[i:fim], final=(fim >= n))
        i = fim

    # fecha texto
    t._finalizar_arquivo_texto()
    caminho = t._caminho_saida
    segmentos = list(t._segmentos)

    if diarizar and segmentos and caminho:
        # roda diarização de forma síncrona
        t._segmentos = segmentos
        # usa o áudio original para diarização via audio_utils.ler_trecho_wav — precisa de WAV temp
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(suffix="_audio.wav")
            os.close(fd)
            with wave.open(tmp, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes((audio * 32767).astype(np.int16).tobytes())
            t._rodar_diarizacao(caminho, tmp)
        finally:
            if tmp and os.path.isfile(tmp):
                # _rodar_diarizacao agora move para PASTA_AUDIO — se ainda existir, limpa
                try:
                    if os.path.isfile(tmp):
                        os.remove(tmp)
                except OSError:
                    pass

    on_status(f"Retranscrição concluída: {os.path.basename(caminho) if caminho else '?'}")
    return caminho
