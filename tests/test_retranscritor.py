# -*- coding: utf-8 -*-
"""T-F2-05 — retranscrição de áudios retidos (FR-2.5)."""
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from retranscritor import listar_audios, retranscrever


class _Seg:
    def __init__(self, text, start, end):
        self.text = text
        self.start = start
        self.end = end


def _escrever_wav(path: Path, segundos=1.0, sr=16000):
    n = int(segundos * sr)
    audio = (np.sin(2 * np.pi * 440 * np.arange(n) / sr) * 0.2 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())
    return path


def test_retranscrever_wav_gera_transcricao_e_diarizada(tmp_path, monkeypatch):
    pasta_tr = tmp_path / "tr"
    pasta_audio = tmp_path / "audio"
    pasta_tr.mkdir()
    pasta_audio.mkdir()
    wav = _escrever_wav(pasta_audio / "transcricao_2026-07-01_10h00_audio.wav", segundos=0.5)

    modelo = MagicMock()
    modelo.transcribe.return_value = (
        [_Seg("ola mundo", 0.0, 0.4)],
        MagicMock(),
    )

    with patch("diarizador.diarizar", return_value=([("FALANTE_01", 0.0, 0.4, "ola mundo")], {})):
        saida = retranscrever(
            str(wav),
            pasta_saida=str(pasta_tr),
            modelo_whisper=modelo,
            diarizar=True,
            criptografar=False,
            identificar_voz=False,
            usar_vozes_conhecidas=False,
        )

    assert saida is not None
    assert Path(saida).is_file()
    texto = Path(saida).read_text(encoding="utf-8")
    assert "ola mundo" in texto.lower() or "ola" in texto.lower()
    diar = list(pasta_tr.glob("*_diarizado*"))
    assert len(diar) >= 1


def test_retranscrever_wav_enc(chave_teste, tmp_path, monkeypatch):
    from crypto_storage import criptografar_wav

    pasta_tr = tmp_path / "tr"
    pasta_audio = tmp_path / "audio"
    pasta_tr.mkdir()
    pasta_audio.mkdir()
    wav = _escrever_wav(pasta_audio / "reuniao_audio.wav", segundos=0.4)
    enc = criptografar_wav(str(wav))
    assert enc.endswith(".wav.enc")

    modelo = MagicMock()
    modelo.transcribe.return_value = ([_Seg("secreto", 0.0, 0.3)], MagicMock())

    with patch("diarizador.diarizar", return_value=([("FALANTE_01", 0.0, 0.3, "secreto")], {})):
        saida = retranscrever(
            enc,
            pasta_saida=str(pasta_tr),
            modelo_whisper=modelo,
            diarizar=True,
            criptografar=False,
            identificar_voz=False,
            usar_vozes_conhecidas=False,
        )
    assert Path(saida).is_file()
    assert "secreto" in Path(saida).read_text(encoding="utf-8").lower()


def test_listar_audios_inclui_data_e_duracao(tmp_path, monkeypatch):
    pasta = tmp_path / "audio"
    pasta.mkdir()
    wav = _escrever_wav(pasta / "a_audio.wav", segundos=2.0)
    items = listar_audios(str(pasta))
    assert len(items) == 1
    assert items[0]["caminho"] == str(wav)
    assert items[0]["duracao_seg"] >= 1.9
    assert "rotulo" in items[0]


def test_retranscrever_nome_deterministico_txt_e_escrita_atomica(
    tmp_path, monkeypatch
):
    import retranscritor

    pasta_tr = tmp_path / "tr"
    pasta_audio = tmp_path / "audio"
    pasta_tr.mkdir()
    pasta_audio.mkdir()
    wav = _escrever_wav(pasta_audio / "reuniao.wav", segundos=0.2)
    modelo = MagicMock()
    modelo.transcribe.return_value = ([_Seg("texto final", 0.0, 0.15)], MagicMock())
    replaces = []
    original = retranscritor.os.replace

    def substituir(origem, destino):
        replaces.append((Path(origem), Path(destino)))
        return original(origem, destino)

    monkeypatch.setattr(retranscritor.os, "replace", substituir)
    saida = retranscrever(
        str(wav),
        pasta_saida=str(pasta_tr),
        nome_base_saida="reuniao_cliente",
        modelo_whisper=modelo,
        diarizar=False,
        gerar_copia_tkpt=False,
        metadados={"duracao_seg": 0.2},
    )

    assert Path(saida).name == "reuniao_cliente.txt"
    assert replaces and replaces[-1][1] == Path(saida)
    assert not list(pasta_tr.glob("*.tmp"))
