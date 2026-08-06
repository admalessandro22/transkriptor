# -*- coding: utf-8 -*-
"""FR-10.G1 — extração não destrutiva de intervalos WAV."""
from __future__ import annotations

import importlib.util
import math
import sys
import wave
from hashlib import sha256
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "recuperar_intervalos_audio.py"


def _carregar():
    spec = importlib.util.spec_from_file_location("recuperar_intervalos_audio", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def modulo():
    return _carregar()


@pytest.fixture
def wav_10s(tmp_path):
    caminho = tmp_path / "original.wav"
    taxa = 16_000
    with wave.open(str(caminho), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(taxa)
        wav.writeframes(b"\x01\x00" * taxa * 10)
    return caminho


def _hash(caminho):
    return sha256(Path(caminho).read_bytes()).hexdigest()


def test_extrair_intervalo_preserva_original(modulo, wav_10s, tmp_path):
    hash_antes = _hash(wav_10s)
    destino = tmp_path / "trecho.wav"

    info = modulo.extrair_intervalo(wav_10s, destino, 2.0, 5.0)

    assert info["duracao_seg"] == pytest.approx(3.0)
    assert info["frames"] == 48_000
    assert info["sample_rate"] == 16_000
    assert info["sha256_original_antes"] == hash_antes
    assert info["sha256_original_depois"] == hash_antes
    assert _hash(wav_10s) == hash_antes
    with wave.open(str(destino), "rb") as wav:
        assert wav.getnframes() == 48_000
        assert wav.getframerate() == 16_000


def test_extrair_intervalo_recusa_sobrescrita(modulo, wav_10s, tmp_path):
    destino = tmp_path / "existente.wav"
    destino.write_bytes(b"preservar")

    with pytest.raises(FileExistsError):
        modulo.extrair_intervalo(wav_10s, destino, 0.0, 1.0)

    assert destino.read_bytes() == b"preservar"


@pytest.mark.parametrize(
    ("inicio", "fim"),
    [(-1, 1), (2, 2), (8, 2), (0, 11), (math.nan, 1), (0, math.inf)],
)
def test_extrair_intervalo_valida_limites(
    modulo, wav_10s, tmp_path, inicio, fim
):
    destino = tmp_path / f"invalido-{inicio}-{fim}.wav"
    with pytest.raises(ValueError):
        modulo.extrair_intervalo(wav_10s, destino, inicio, fim)
    assert not destino.exists()


def test_extrair_intervalo_rejeita_wav_invalido(modulo, tmp_path):
    origem = tmp_path / "invalido.wav"
    origem.write_bytes(b"isto nao e wav")
    destino = tmp_path / "saida.wav"

    with pytest.raises(ValueError, match="WAV"):
        modulo.extrair_intervalo(origem, destino, 0, 1)

    assert origem.read_bytes() == b"isto nao e wav"
    assert not destino.exists()


def test_extracao_le_em_blocos_limitados(modulo, wav_10s, tmp_path, monkeypatch):
    original_open = modulo.wave.open
    leituras = []

    class LeitorObservado:
        def __init__(self, leitor):
            self._leitor = leitor

        def __enter__(self):
            self._leitor.__enter__()
            return self

        def __exit__(self, *args):
            return self._leitor.__exit__(*args)

        def readframes(self, quantidade):
            leituras.append(quantidade)
            return self._leitor.readframes(quantidade)

        def __getattr__(self, nome):
            return getattr(self._leitor, nome)

    def abrir(caminho, modo=None):
        resultado = original_open(caminho, modo)
        if modo == "rb":
            return LeitorObservado(resultado)
        return resultado

    monkeypatch.setattr(modulo.wave, "open", abrir)
    modulo.extrair_intervalo(wav_10s, tmp_path / "stream.wav", 0, 10)

    assert len(leituras) > 1
    assert max(leituras) <= modulo.BLOCO_FRAMES
