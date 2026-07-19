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


def test_reforcar_rotulo_anti_eco_mantem_rotulo(tmp_path):
    """FR-5.6: mic fraco vs loopback forte (eco do alto-falante) não vira VOCÊ."""
    from config import MARGEM_ANTI_ECO

    assert MARGEM_ANTI_ECO == 1.5
    caminho = tmp_path / "mic_eco.wav"
    sr = 16000
    # mic com energia acima do limiar mas fraca frente ao loopback
    dados = (np.ones(sr, dtype=np.float32) * 0.15 * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(dados.tobytes())

    resultado = [("FALANTE_01", 0.0, 1.0, "voz do outro")]
    # rms_mic ≈ 0.15; loopback 0.4 → 0.15 <= 0.4 * 1.5 → eco
    reforcado = reforcar_rotulo_por_mic(
        resultado,
        str(caminho),
        limiar_rms=0.1,
        rotulo_usuario="VOCÊ",
        sample_rate=sr,
        rms_loopback_por_segmento=[0.4],
        margem_anti_eco=MARGEM_ANTI_ECO,
    )
    assert reforcado[0][0] == "FALANTE_01"


def test_reforcar_rotulo_fala_real_vira_voce(tmp_path):
    """FR-5.6: fala real no mic (rms_mic >> loopback) vira VOCÊ."""
    from config import MARGEM_ANTI_ECO

    caminho = tmp_path / "mic_real.wav"
    sr = 16000
    dados = (np.ones(sr, dtype=np.float32) * 0.5 * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(dados.tobytes())

    resultado = [("FALANTE_00", 0.0, 1.0, "eu falo")]
    # rms_mic ≈ 0.5; loopback 0.2 → 0.5 > 0.2 * 1.5 = 0.3 → fala real
    reforcado = reforcar_rotulo_por_mic(
        resultado,
        str(caminho),
        limiar_rms=0.1,
        rotulo_usuario="VOCÊ",
        sample_rate=sr,
        rms_loopback_por_segmento=[0.2],
        margem_anti_eco=MARGEM_ANTI_ECO,
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