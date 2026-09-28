# -*- coding: utf-8 -*-
"""T-13.E1 — TKAS/1: streaming autenticado, sem primitiva reinventada."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from crypto_stream import ErroTKAS, TAMANHO_CHUNK, encrypt_file, iter_decrypt_file

CHAVE = b"k" * 32


def _bytes_aleatorios(n: int, seed: int = 7) -> bytes:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=n, dtype=np.uint8).tobytes()


def _roundtrip(dados: bytes, tmp_path: Path) -> bytes:
    origem = tmp_path / "plano.bin"
    destino = tmp_path / "plano.bin.tks"
    origem.write_bytes(dados)
    ref = encrypt_file(origem, destino, CHAVE)
    assert destino.is_file()
    import hashlib

    assert ref.sha256 == hashlib.sha256(destino.read_bytes()).hexdigest()
    return b"".join(iter_decrypt_file(destino, CHAVE))


def test_roundtrip_pequeno(tmp_path):
    dados = _bytes_aleatorios(1000)
    assert _roundtrip(dados, tmp_path) == dados


def test_roundtrip_multibloco(tmp_path):
    dados = _bytes_aleatorios(2_600_000)
    assert _roundtrip(dados, tmp_path) == dados


def _partes(caminho: Path):
    bruto = caminho.read_bytes()
    assert bruto[:4] == b"TKAS" and bruto[4:5] == b"\x01"
    tamanho = int.from_bytes(bruto[5:9], "little")
    cabeca = 9 + 32
    corpo = bruto[cabeca:]
    blocos, resto = [], corpo
    while resto:
        n = min(tamanho, len(resto) - 16)
        blocos.append(resto[: n + 16])
        resto = resto[n + 16 :]
    return bruto[:cabeca], blocos


def test_truncado_falha(tmp_path):
    destino = tmp_path / "a.tks"
    (tmp_path / "a.bin").write_bytes(_bytes_aleatorios(2_100_000))
    encrypt_file(tmp_path / "a.bin", destino, CHAVE)
    destino.write_bytes(destino.read_bytes()[:-10])
    with pytest.raises(Exception):
        b"".join(iter_decrypt_file(destino, CHAVE))


def test_chunk_alterado_falha(tmp_path):
    destino = tmp_path / "b.tks"
    (tmp_path / "b.bin").write_bytes(_bytes_aleatorios(2_100_000))
    encrypt_file(tmp_path / "b.bin", destino, CHAVE)
    cabeca, blocos = _partes(destino)
    corrompido = bytearray(blocos[0])
    corrompido[5] ^= 0xFF
    destino.write_bytes(cabeca + bytes(corrompido) + b"".join(blocos[1:]))
    with pytest.raises(Exception):
        b"".join(iter_decrypt_file(destino, CHAVE))


def test_chunk_reordenado_falha(tmp_path):
    destino = tmp_path / "c.tks"
    (tmp_path / "c.bin").write_bytes(_bytes_aleatorios(2_100_000))
    encrypt_file(tmp_path / "c.bin", destino, CHAVE)
    cabeca, blocos = _partes(destino)
    assert len(blocos) >= 2
    destino.write_bytes(cabeca + b"".join(reversed(blocos)))
    with pytest.raises(Exception):
        b"".join(iter_decrypt_file(destino, CHAVE))


def test_chunk_duplicado_falha(tmp_path):
    destino = tmp_path / "d.tks"
    (tmp_path / "d.bin").write_bytes(_bytes_aleatorios(2_100_000))
    encrypt_file(tmp_path / "d.bin", destino, CHAVE)
    cabeca, blocos = _partes(destino)
    destino.write_bytes(cabeca + blocos[0] + b"".join(blocos))
    with pytest.raises(Exception):
        b"".join(iter_decrypt_file(destino, CHAVE))


def test_sem_tag_final_falha(tmp_path):
    from nacl.bindings import (
        crypto_secretstream_xchacha20poly1305_TAG_MESSAGE,
        crypto_secretstream_xchacha20poly1305_init_push,
        crypto_secretstream_xchacha20poly1305_push,
        crypto_secretstream_xchacha20poly1305_state,
    )

    from crypto_stream import _chave_stream

    destino = tmp_path / "e.tks"
    cabecalho = b"TKAS\x01" + (1_048_576).to_bytes(4, "little")
    with open(destino, "wb") as f:
        f.write(cabecalho)
        estado = crypto_secretstream_xchacha20poly1305_state()
        cabeca = crypto_secretstream_xchacha20poly1305_init_push(estado, _chave_stream(CHAVE))
        f.write(cabeca)
        from crypto_stream import _ad_chunk

        for i, parte in enumerate((b"a" * 100, b"b" * 100)):
            f.write(
                crypto_secretstream_xchacha20poly1305_push(
                    estado, parte, _ad_chunk(cabecalho, i), crypto_secretstream_xchacha20poly1305_TAG_MESSAGE
                )
            )
    with pytest.raises(Exception):
        b"".join(iter_decrypt_file(destino, CHAVE))


def test_chave_errada_falha(tmp_path):
    destino = tmp_path / "f.tks"
    (tmp_path / "f.bin").write_bytes(_bytes_aleatorios(500))
    encrypt_file(tmp_path / "f.bin", destino, CHAVE)
    with pytest.raises(Exception):
        b"".join(iter_decrypt_file(destino, b"y" * 32))


def test_tkas_rejeita_sufixo_apos_chunk_final_cheio(tmp_path):
    origem = tmp_path / "audio.wav"
    origem.write_bytes(b"A" * TAMANHO_CHUNK)
    destino = tmp_path / "audio.tks"
    encrypt_file(origem, destino, CHAVE)
    with destino.open("ab") as arquivo:
        arquivo.write(b"NAO-AUTENTICADO")
    with pytest.raises(ErroTKAS, match="após tag final"):
        list(iter_decrypt_file(destino, CHAVE))


def test_validacao_de_cifra_nao_acumula_chunks(tmp_path, monkeypatch):
    import crypto_stream

    origem = tmp_path / "curto.wav"
    origem.write_bytes(b"conteudo")
    vivos = [0]
    pico = [0]

    class Rastreado:
        def __init__(self):
            vivos[0] += 1
            pico[0] = max(pico[0], vivos[0])

        def __del__(self):
            vivos[0] -= 1

    def iterador_fake(*_args):
        for _ in range(100):
            yield Rastreado()

    monkeypatch.setattr(crypto_stream, "iter_decrypt_file", iterador_fake)
    encrypt_file(origem, tmp_path / "curto.tks", CHAVE)
    assert pico[0] <= 2


def test_audio_tks_no_reader(chave_teste, tmp_path):
    from crypto_storage import obter_chave_mestra

    mestra = obter_chave_mestra()
    sr, n = 16000, 8000
    audio = (np.sin(2 * np.pi * 440 * np.arange(n) / sr) * 0.3 * 32767).astype(np.int16)
    wav = tmp_path / "fala.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())
    tks = tmp_path / "fala.wav.tks"
    encrypt_file(wav, tks, mestra)
    from audio_reader import AudioSource, inspect_audio, iter_audio

    info = inspect_audio(tks, AudioSource.MICROPHONE)
    assert (info.sample_rate, info.total_frames) == (sr, n)
    amostras = np.concatenate([b.samples for b in iter_audio(tks, AudioSource.MICROPHONE)])
    assert np.allclose(amostras, audio.astype(np.float32) / 32768.0, atol=1e-4)


def test_inspecao_tks_autentica_ate_o_fim(chave_teste, tmp_path):
    from audio_reader import AudioSource, inspect_audio
    from crypto_storage import obter_chave_mestra

    wav = tmp_path / "audio.wav"
    with wave.open(str(wav), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(16000)
        arquivo.writeframes(b"\x00\x00" * ((2 * TAMANHO_CHUNK - 44) // 2))
    tks = tmp_path / "audio.tks"
    encrypt_file(wav, tks, obter_chave_mestra())
    with tks.open("ab") as arquivo:
        arquivo.write(b"sufixo")
    with pytest.raises(ErroTKAS, match="após tag final"):
        inspect_audio(tks, AudioSource.LOOPBACK)
