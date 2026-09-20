# -*- coding: utf-8 -*-
"""Leitura tipada de áudio por fonte (T-13.C2; streaming ampliado em C3)."""
from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterator

import numpy as np

from config import AUDIO_BLOCO_MAX_SEG, AUDIO_CIFRADO_LEGADO_MAX_BYTES, SAMPLE_RATE


class UnsupportedAudioFormat(ValueError):
    """Formato PCM não implementado explicitamente."""


class AudioSource(StrEnum):
    LOOPBACK = "loopback"
    MICROPHONE = "microphone"


@dataclass(frozen=True)
class AudioInfo:
    sample_rate: int
    channels: int
    sample_width: int
    total_frames: int
    source: AudioSource


@dataclass(frozen=True)
class AudioChunk:
    start_frame: int
    samples: np.ndarray


_LARGURAS_SUPORTADAS = (2, 3, 4)
_MAGIC_TKS = b"TKAS"


def _eh_tks(path: Path) -> bool:
    if path.name.lower().endswith(".tks"):
        return True
    try:
        with open(path, "rb") as arquivo:
            return arquivo.read(4) == _MAGIC_TKS
    except OSError:
        return False


def _parse_cabecalho_wav(buf: bytes):
    """RIFF manual: (sr, canais, largura, offset_dados, bytes_dados) ou None."""
    import struct

    if len(buf) < 16 or buf[:4] != b"RIFF":
        return None
    pos = 12
    sr = canais = largura = None
    while pos + 8 <= len(buf):
        tag, tamanho = buf[pos : pos + 4], struct.unpack("<I", buf[pos + 4 : pos + 8])[0]
        corpo = pos + 8
        if tag == b"fmt " and tamanho >= 16 and corpo + 16 <= len(buf):
            formato, canais, sr = struct.unpack("<HHI", buf[corpo : corpo + 8])
            largura = struct.unpack("<H", buf[corpo + 14 : corpo + 16])[0] // 8
            if formato != 1:
                raise UnsupportedAudioFormat("WAV não-PCM rejeitado")
        elif tag == b"data":
            if sr is None or largura not in _LARGURAS_SUPORTADAS:
                if sr is not None:
                    raise UnsupportedAudioFormat(
                        f"PCM {(largura or 0) * 8}-bit não implementado"
                    )
                return None
            return sr, canais, largura, corpo, tamanho
        pos = corpo + tamanho + (tamanho % 2)
        if pos > len(buf):
            return None
    return None


def _chave_tks() -> bytes:
    from crypto_storage import obter_chave_mestra

    return obter_chave_mestra()


def _iter_tks(path: Path, source: AudioSource, max_seconds: float) -> Iterator[AudioChunk]:
    """Blocos de WAV dentro de TKAS sem materializar o plaintext (T-13.E1)."""
    from crypto_stream import iter_decrypt_file

    acumulador = bytearray()
    cabecalho = None
    resto = b""
    inicio_frame = 0
    for pedaco in iter_decrypt_file(path, _chave_tks()):
        acumulador.extend(pedaco)
        if cabecalho is None:
            parsed = _parse_cabecalho_wav(bytes(acumulador))
            if parsed is None:
                continue
            cabecalho = parsed
            resto = bytes(acumulador[cabecalho[3] :])
            acumulador.clear()
        else:
            resto = resto + bytes(acumulador)
            acumulador.clear()
        sr, canais, largura, _, _ = cabecalho
        quadros_bloco = max(1, int(sr * max_seconds))
        bloco_bytes = quadros_bloco * canais * largura
        while len(resto) >= bloco_bytes:
            yield AudioChunk(
                start_frame=inicio_frame,
                samples=_converter_para_float32(resto[:bloco_bytes], largura, canais),
            )
            inicio_frame += quadros_bloco
            resto = resto[bloco_bytes:]
    if cabecalho is None:
        raise UnsupportedAudioFormat("TKAS sem WAV válido")
    if resto:
        sr, canais, largura, _, _ = cabecalho
        yield AudioChunk(
            start_frame=inicio_frame,
            samples=_converter_para_float32(resto, largura, canais),
        )


def _inspect_tks(path: Path, source: AudioSource) -> AudioInfo:
    from crypto_stream import iter_decrypt_file

    acumulador = bytearray()
    for pedaco in iter_decrypt_file(path, _chave_tks()):
        acumulador.extend(pedaco)
        parsed = _parse_cabecalho_wav(bytes(acumulador))
        if parsed is not None:
            sr, canais, largura, _, bytes_dados = parsed
            quadro = canais * largura
            return AudioInfo(sr, canais, largura, bytes_dados // max(1, quadro), source)
    raise UnsupportedAudioFormat("TKAS sem WAV válido")


def _abrir_wav_plano(path: Path) -> tuple[object, object | None]:
    """Abre WAV plaintext; nunca `wave.open` sobre ciphertext.

    `.wav.enc` legado é decifrado integralmente via API tipada
    (`crypto_storage.ler_bytes_arquivo`) e respeita o limite de `config.py`;
    o `wave.open` atua sobre o plaintext em memória.
    """
    if path.name.lower().endswith(".wav.enc"):
        tamanho = path.stat().st_size
        if tamanho > AUDIO_CIFRADO_LEGADO_MAX_BYTES:
            raise UnsupportedAudioFormat(
                f"cifrado legado excede {AUDIO_CIFRADO_LEGADO_MAX_BYTES} bytes"
            )
        from crypto_storage import ler_bytes_arquivo

        plano = ler_bytes_arquivo(str(path))
        buffer = io.BytesIO(plano)
        return wave.open(buffer, "rb"), buffer
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return wave.open(str(path), "rb"), None


def _converter_para_float32(raw: bytes, sample_width: int, channels: int) -> np.ndarray:
    if sample_width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 3:
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        ints = (
            arr[:, 0].astype(np.int32)
            | (arr[:, 1].astype(np.int32) << 8)
            | (arr[:, 2].astype(np.int32) << 16)
        )
        ints = np.where(ints >= 1 << 23, ints - (1 << 24), ints)
        data = ints.astype(np.float32) / 8388608.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise UnsupportedAudioFormat(f"PCM {sample_width * 8}-bit não implementado")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data.astype(np.float32)


def inspect_audio(path: Path, source: AudioSource) -> AudioInfo:
    if _eh_tks(Path(path)):
        return _inspect_tks(Path(path), source)
    wav, detentor = _abrir_wav_plano(Path(path))
    try:
        canais = wav.getnchannels()
        largura = wav.getsampwidth()
        taxa = wav.getframerate()
        total = wav.getnframes()
    finally:
        try:
            wav.close()
        finally:
            if detentor is not None:
                detentor.close()
    if largura not in _LARGURAS_SUPORTADAS:
        raise UnsupportedAudioFormat(f"PCM {largura * 8}-bit não implementado")
    return AudioInfo(
        sample_rate=int(taxa),
        channels=int(canais),
        sample_width=int(largura),
        total_frames=int(total),
        source=source,
    )


def iter_audio(
    path: Path, source: AudioSource, max_seconds: float = AUDIO_BLOCO_MAX_SEG
) -> Iterator[AudioChunk]:
    if _eh_tks(Path(path)):
        yield from _iter_tks(Path(path), source, max_seconds)
        return
    info = inspect_audio(Path(path), source)
    tamanho_bloco = max(1, int(info.sample_rate * max_seconds))
    wav, detentor = _abrir_wav_plano(Path(path))
    try:
        inicio = 0
        while True:
            raw = wav.readframes(tamanho_bloco)
            if not raw:
                break
            yield AudioChunk(
                start_frame=inicio,
                samples=_converter_para_float32(raw, info.sample_width, info.channels),
            )
            inicio += tamanho_bloco
    finally:
        try:
            wav.close()
        finally:
            if detentor is not None:
                detentor.close()


def iter_audio_16k(
    path: Path, source: AudioSource, max_seconds: float = AUDIO_BLOCO_MAX_SEG
) -> Iterator[AudioChunk]:
    """Blocos reamostrados para 16 kHz; a origem temporal segue a taxa do arquivo."""
    info = inspect_audio(Path(path), source)
    for bloco in iter_audio(path, source, max_seconds):
        if info.sample_rate == SAMPLE_RATE or bloco.samples.size == 0:
            yield bloco
            continue
        n_out = max(1, int(bloco.samples.size * SAMPLE_RATE / info.sample_rate))
        x_old = np.linspace(0, 1, num=bloco.samples.size, endpoint=False)
        x_new = np.linspace(0, 1, num=n_out, endpoint=False)
        yield AudioChunk(
            start_frame=bloco.start_frame,
            samples=np.interp(x_new, x_old, bloco.samples).astype(np.float32),
        )
