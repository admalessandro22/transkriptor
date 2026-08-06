# -*- coding: utf-8 -*-
"""FR-10.C — captura leve com processamento somente após a reunião."""
from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from transcricao_core import Transcritor


REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def transcritor_posterior(tmp_path):
    t = Transcritor(
        pasta_saida=str(tmp_path),
        processar_ao_vivo=False,
        capturar_mic=False,
        criptografar=False,
    )
    t._abrir_arquivo()
    yield t
    t._fechar_arquivos_abertos()


def test_modo_posterior_nao_carrega_modelo(monkeypatch, tmp_path):
    t = Transcritor(
        pasta_saida=str(tmp_path),
        processar_ao_vivo=False,
        capturar_mic=False,
        criptografar=False,
    )
    monkeypatch.setattr(t, "_carregar_modelo", lambda: pytest.fail("Whisper carregado"))
    monkeypatch.setattr(t, "_capturar", lambda: t._stop.wait())

    t.start()
    t.stop()


def test_modo_posterior_grava_todos_blocos_em_ordem(tmp_path):
    t = Transcritor(
        pasta_saida=str(tmp_path),
        processar_ao_vivo=False,
        capturar_mic=False,
        criptografar=False,
    )
    t._abrir_arquivo()
    for valor in (0.1, 0.2, 0.3):
        t._gravar_audio_bloco(np.full(1600, valor, dtype=np.float32))
    caminho = t._caminho_wav
    t._fechar_arquivos_abertos()

    with wave.open(caminho, "rb") as wav:
        frames = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    assert frames.size == 4800
    medias = [frames[i : i + 1600].mean() for i in range(0, frames.size, 1600)]
    assert medias[0] < medias[1] < medias[2]


def test_stop_expoe_audio_preservado(tmp_path, monkeypatch):
    t = Transcritor(
        pasta_saida=str(tmp_path),
        processar_ao_vivo=False,
        capturar_mic=False,
        criptografar=False,
    )
    monkeypatch.setattr(t, "_capturar", lambda: t._stop.wait())

    t.start()
    t.stop()

    assert t.audios_preservados
    assert all(Path(path).is_file() for path in t.audios_preservados)
    with wave.open(t.audios_preservados[0], "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000


def test_importar_captura_nao_importa_bibliotecas_de_ia():
    codigo = (
        "import sys; import transcricao_core; "
        "print(any(nome in sys.modules for nome in "
        "('faster_whisper', 'ctranslate2', 'speechbrain')))"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    assert resultado.stdout.strip() == "False"


def test_metricas_modo_posterior_sem_descartes(transcritor_posterior):
    metricas = transcritor_posterior.metricas_captura()
    assert metricas["blocos_descartados"] == 0
    assert metricas["falhas_gravacao"] == 0


def test_flush_periodico_e_contagem_de_frames(monkeypatch, transcritor_posterior):
    flush = MagicMock()
    monkeypatch.setattr(transcritor_posterior, "_flush_audio", flush)
    transcritor_posterior._segundos_desde_flush = 5

    transcritor_posterior._gravar_audio_bloco(
        np.zeros(16000, dtype=np.float32)
    )

    flush.assert_called_once()
    assert transcritor_posterior.metricas_captura()["frames_gravados"] == 16000
