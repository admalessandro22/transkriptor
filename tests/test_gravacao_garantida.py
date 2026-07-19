# -*- coding: utf-8 -*-
"""T-F2-01+ — gravação local garantida do áudio da reunião (FR-2.1, FR-2.8)."""
import shutil
import threading
import time
import wave
from collections import namedtuple
from unittest.mock import MagicMock, patch

import numpy as np

from config import MIN_DISCO_LIVRE_GB
from transcricao_core import Transcritor


def test_wav_sempre_aberto_mesmo_sem_diarizacao(tmp_path):
    """FR-2.1: _abrir_arquivo sempre cria WAV, com diarização off."""
    t = Transcritor(
        pasta_saida=str(tmp_path),
        diarizar_ao_final=False,
        capturar_mic=False,
        criptografar=False,
    )
    t._abrir_arquivo()
    assert t._caminho_wav is not None
    assert t._caminho_wav.endswith("_audio.wav")
    assert t._wav is not None
    t._wav.close()
    t._wav = None


def test_stop_sem_diarizacao_move_wav_para_pasta_audio(tmp_path, monkeypatch):
    """FR-2.1: após stop() com diarização off, WAV existe em PASTA_AUDIO com frames > 0."""
    pasta_audio = tmp_path / "audio"
    monkeypatch.setattr("transcricao_core.PASTA_AUDIO", str(pasta_audio))
    monkeypatch.setattr("config.PASTA_AUDIO", str(pasta_audio))

    t = Transcritor(
        pasta_saida=str(tmp_path),
        diarizar_ao_final=False,
        capturar_mic=False,
        criptografar=False,
    )
    t._abrir_arquivo()
    # grava frames reais no WAV (caminho de produção via _transcrever_bloco)
    audio = np.full(8000, 0.15, dtype=np.float32)
    t._modelo = MagicMock()
    t._modelo.transcribe.return_value = ([], MagicMock())
    t._transcrever_bloco(audio)
    t.rodando = True
    t._thread_cap = threading.Thread(target=lambda: None, daemon=True)
    t._thread_proc = threading.Thread(target=lambda: None, daemon=True)
    t.stop()

    wavs = list(pasta_audio.glob("*_audio.wav"))
    assert len(wavs) == 1, (
        f"esperado 1 wav em {pasta_audio}, "
        f"got {list(pasta_audio.iterdir()) if pasta_audio.exists() else 'missing'}"
    )
    with wave.open(str(wavs[0]), "rb") as w:
        assert w.getnframes() > 0
    assert not list(tmp_path.glob("*_audio.wav"))


def test_stop_com_diarizacao_move_wav_no_finally(tmp_path, monkeypatch):
    """FR-2.1: com diarização, WAV é movido ao fim (não apagado)."""
    pasta_audio = tmp_path / "audio"
    monkeypatch.setattr("transcricao_core.PASTA_AUDIO", str(pasta_audio))

    t = Transcritor(
        pasta_saida=str(tmp_path),
        diarizar_ao_final=True,
        capturar_mic=False,
        criptografar=False,
        identificar_voz=False,
        usar_vozes_conhecidas=False,
    )
    t._abrir_arquivo()
    # grava frames mínimos e segmentos para acionar diarização
    assert t._wav is not None
    frames = (np.full(16000, 0.1) * 32767).astype(np.int16).tobytes()
    t._wav.writeframes(frames)
    t._segmentos = [(0.0, 0.5, "ola")]
    t.rodando = True
    t._thread_cap = threading.Thread(target=lambda: None, daemon=True)
    t._thread_proc = threading.Thread(target=lambda: None, daemon=True)

    with patch("diarizador.diarizar", return_value=([("FALANTE_01", 0.0, 0.5, "ola")], {})):
        t.stop()
        if t._thread_diar:
            t._thread_diar.join(timeout=10)

    wavs = list(pasta_audio.glob("*_audio.wav"))
    assert len(wavs) == 1
    with wave.open(str(wavs[0]), "rb") as w:
        assert w.getnframes() > 0
    assert not list(tmp_path.glob("*_audio.wav"))


def test_aviso_disco_baixo_no_start(tmp_path, monkeypatch):
    """FR-2.8: disco < MIN_DISCO_LIVRE_GB gera status de aviso; gravação segue."""
    statuses = []
    t = Transcritor(
        pasta_saida=str(tmp_path),
        diarizar_ao_final=False,
        capturar_mic=False,
        criptografar=False,
        on_status=statuses.append,
    )
    t._modelo = MagicMock()
    livre_baixo = int((MIN_DISCO_LIVRE_GB - 0.5) * (1024**3))
    DU = namedtuple("usage", "total used free")
    usage = DU(total=100 * 1024**3, used=99 * 1024**3, free=livre_baixo)

    rec = MagicMock()
    rec.__enter__ = MagicMock(return_value=rec)
    rec.__exit__ = MagicMock(return_value=False)
    rec.record = lambda n: np.zeros((n, 1), dtype=np.float32)
    mic = MagicMock()
    mic.recorder.return_value = rec

    with patch("transcricao_core.shutil.disk_usage", return_value=usage), patch.object(
        t, "_abrir_loopback", return_value=mic
    ):
        t.start()
        time.sleep(0.15)
        t.stop()

    assert any(
        "disco" in s.lower() or "espaço" in s.lower() or "espaco" in s.lower()
        for s in statuses
    ), statuses
    assert MIN_DISCO_LIVRE_GB >= 2
