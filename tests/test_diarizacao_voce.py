# -*- coding: utf-8 -*-
"""Testes de rótulo VOCÊ na diarização (Fase 7 — FR-7.6/7.7/7.8)."""
import wave
from unittest.mock import patch

import numpy as np

from diarizador import (
    aplicar_identificacao_usuario,
    diarizar,
    reforcar_rotulo_por_mic,
    segmento_tem_voz_mic,
)


def test_aplicar_identificacao_usuario_rotula_cluster_similar():
    resultado = [
        ("FALANTE_00", 0.0, 1.0, "outro"),
        ("FALANTE_01", 1.0, 2.0, "eu"),
    ]
    centroides = [
        np.array([0.0, 1.0], dtype=np.float32),
        np.array([0.95, 0.05], dtype=np.float32),
    ]
    perfil = np.array([1.0, 0.0], dtype=np.float32)
    rotulado = aplicar_identificacao_usuario(
        resultado, centroides, perfil, limiar=0.72, rotulo_usuario="VOCÊ"
    )
    rotulos = [r[0] for r in rotulado]
    assert rotulos == ["FALANTE_00", "VOCÊ"]


def test_aplicar_identificacao_sem_perfil_mantem_falante():
    resultado = [("FALANTE_00", 0.0, 1.0, "x")]
    rotulado = aplicar_identificacao_usuario(
        resultado, [np.array([1.0, 0.0], dtype=np.float32)], None, limiar=0.72
    )
    assert rotulado[0][0] == "FALANTE_00"


def test_segmento_tem_voz_mic_detecta_energia():
    alto = np.ones(1600, dtype=np.float32) * 0.5
    baixo = np.zeros(1600, dtype=np.float32)
    assert segmento_tem_voz_mic(alto, limiar_rms=0.1) is True
    assert segmento_tem_voz_mic(baixo, limiar_rms=0.1) is False


def test_reforcar_rotulo_por_mic(tmp_path):
    caminho = tmp_path / "mic.wav"
    sr = 16000
    dados = (np.ones(sr, dtype=np.float32) * 0.4 * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(dados.tobytes())

    resultado = [("FALANTE_00", 0.0, 1.0, "fala minha")]
    reforcado = reforcar_rotulo_por_mic(
        resultado, str(caminho), limiar_rms=0.1, rotulo_usuario="VOCÊ", sample_rate=sr
    )
    assert reforcado[0][0] == "VOCÊ"


def _mic_wav_alto(tmp_path, duracao_seg=1.0, sr=16000):
    caminho = tmp_path / "mic.wav"
    n = int(sr * duracao_seg)
    dados = (np.ones(n, dtype=np.float32) * 0.4 * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(dados.tobytes())
    return caminho


def test_diarizar_um_segmento_perfil_e_mic_rotula_voce(tmp_path):
    segmentos = [(0.0, 1.0, "so eu")]
    trechos = [np.ones(8000, dtype=np.float32)]
    perfil = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    emb = np.array([0.95, 0.05, 0.0], dtype=np.float32)
    mic = _mic_wav_alto(tmp_path)

    with patch("diarizador._carregar_encoder", return_value=object()):
        with patch("diarizador._extrair_embedding", return_value=emb):
            resultado = diarizar(
                trechos,
                segmentos,
                perfil_usuario=perfil,
                limiar_identificacao=0.72,
                rotulo_usuario="VOCÊ",
                identificar_ativo=True,
                caminho_mic_wav=str(mic),
                limiar_rms_mic=0.1,
            )
    assert len(resultado) == 1
    assert resultado[0][0] == "VOCÊ"


def test_diarizar_com_perfil_mock_rotula_voce():
    segmentos = [(0.0, 1.0, "a"), (1.0, 2.0, "b")]
    trechos = [np.ones(8000, dtype=np.float32), np.ones(8000, dtype=np.float32)]
    perfil = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    emb0 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    emb1 = np.array([0.9, 0.1, 0.0], dtype=np.float32)

    def _fake_emb(_encoder, trecho):
        if trecho is trechos[1] or np.allclose(trecho, trechos[1]):
            return emb1
        return emb0

    with patch("diarizador._carregar_encoder", return_value=object()):
        with patch("diarizador._extrair_embedding", side_effect=_fake_emb):
            resultado = diarizar(
                trechos,
                segmentos,
                num_falantes=2,
                perfil_usuario=perfil,
                limiar_identificacao=0.72,
                rotulo_usuario="VOCÊ",
                identificar_ativo=True,
            )
    rotulos = {r[0] for r in resultado}
    assert "VOCÊ" in rotulos
    assert any(r[0] == "FALANTE_01" or r[0].startswith("FALANTE") for r in resultado)