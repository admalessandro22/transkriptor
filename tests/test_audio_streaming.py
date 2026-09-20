# -*- coding: utf-8 -*-
"""T-13.C3 — áudio longo em blocos e formatos PCM explícitos."""
from __future__ import annotations

import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from audio_reader import AudioSource, UnsupportedAudioFormat, inspect_audio, iter_audio


SR = 16000


class _Seg:
    def __init__(self, text, start, end):
        self.text = text
        self.start = start
        self.end = end


def _escrever_wav(path: Path, segundos=1.0, sr=SR, largura=2, canais=1, freq=440.0):
    n = int(segundos * sr)
    t = np.arange(n) / sr
    seno = np.sin(2 * np.pi * freq * t) * 0.2
    if largura == 2:
        raw = (seno * 32767).astype(np.int16).tobytes()
    elif largura == 3:
        ints = (seno * 8388607).astype(np.int32)
        raw = b"".join(int(v).to_bytes(3, "little", signed=True) for v in ints)
    elif largura == 4:
        raw = (seno * 2147483647).astype(np.int32).tobytes()
    else:
        raise ValueError("largura de teste inválida")
    if canais > 1:
        quadros = [raw[i : i + largura] for i in range(0, len(raw), largura)]
        raw = b"".join(q * canais for q in quadros)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(canais)
        w.setsampwidth(largura)
        w.setframerate(sr)
        w.writeframes(raw)
    return path


def test_audio_duas_horas_nao_le_completo(tmp_path, monkeypatch):
    """Nenhuma leitura única pode materializar o waveform de 2 h."""
    import wave as _wave

    wav = _escrever_wav(tmp_path / "longo.wav", segundos=60.0)
    max_lidos = [0]
    original = _wave.Wave_read.readframes

    def _espiar(self, n):
        max_lidos[0] = max(max_lidos[0], n)
        return original(self, n)

    monkeypatch.setattr(_wave.Wave_read, "readframes", _espiar)
    from retranscritor import retranscrever

    modelo = MagicMock()
    modelo.transcribe.return_value = ([_Seg("ok", 0.0, 0.5)], MagicMock())
    retranscrever(
        str(wav),
        pasta_saida=str(tmp_path / "tr"),
        nome_base_saida="c3-blocos",
        modelo_whisper=modelo,
        diarizar=False,
    )
    assert max_lidos[0] <= SR * 30, f"leitura única de {max_lidos[0]} frames"


def test_pcm24_nao_vira_uint8(tmp_path):
    """PCM 24-bit usa conversão própria; nunca cai no ramo uint8 genérico."""
    wav = _escrever_wav(tmp_path / "p24.wav", segundos=0.5, largura=3)
    info = inspect_audio(wav, AudioSource.LOOPBACK)
    assert info.sample_width == 3
    blocos = list(iter_audio(wav, AudioSource.LOOPBACK))
    pico = max(abs(b.samples).max(initial=0.0) for b in blocos)
    assert 0.15 < pico <= 1.0


def test_chunk_riff_extra_preserva_duracao(tmp_path):
    """Chunks RIFF extras (ex.: LIST) não deslocam duração/amostra."""
    wav = _escrever_wav(tmp_path / "base.wav", segundos=1.0)
    bruto = bytearray(wav.read_bytes())
    assert bruto[:4] == b"RIFF"
    pos_data = bruto.find(b"data")
    assert pos_data > 0
    extra = b"LIST" + struct.pack("<I", 4) + b"INFO"
    bruto[pos_data:pos_data] = extra
    bruto[4:8] = struct.pack("<I", len(bruto) - 8)
    wav.write_bytes(bytes(bruto))
    info = inspect_audio(wav, AudioSource.LOOPBACK)
    assert info.total_frames == SR
    blocos = list(iter_audio(wav, AudioSource.LOOPBACK))
    total = sum(b.samples.size for b in blocos)
    assert total == SR


def test_cifrado_legado_excede_limite_com_erro_claro(chave_teste, tmp_path, monkeypatch):
    """`.enc` acima do limite da config falha explícito, sem ler tudo."""
    from crypto_storage import criptografar_wav

    wav = _escrever_wav(tmp_path / "mic.wav", segundos=0.2)
    enc = Path(criptografar_wav(str(wav)))
    monkeypatch.setattr("audio_reader.AUDIO_CIFRADO_LEGADO_MAX_BYTES", 10)
    with pytest.raises(UnsupportedAudioFormat):
        inspect_audio(enc, AudioSource.MICROPHONE)
