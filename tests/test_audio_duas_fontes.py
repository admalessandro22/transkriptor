# -*- coding: utf-8 -*-
"""T-13.C2 — STT por fonte (loopback + microfone) com fusão cronológica."""
from __future__ import annotations

import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from audio_fontes import SegmentoSTT, mesclar_segmentos, transcrever_fonte
from audio_reader import AudioSource, UnsupportedAudioFormat, inspect_audio, iter_audio


class _Seg:
    def __init__(self, text, start, end):
        self.text = text
        self.start = start
        self.end = end


def _escrever_wav(path: Path, segundos=1.0, sr=16000, freq=440.0):
    n = int(segundos * sr)
    audio = (np.sin(2 * np.pi * freq * np.arange(n) / sr) * 0.2 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())
    return path


def _modelo_com(falas):
    """Modelo fake: cada chamada a transcribe devolve as falas configuradas."""
    modelo = MagicMock()
    modelo.transcribe.return_value = (
        [_Seg(texto, ini, fim) for texto, ini, fim in falas],
        MagicMock(),
    )
    return modelo


def test_frase_exclusiva_mic_aparece(tmp_path, chave_teste):
    """Fala só no mic (texto próprio) entra no resultado — não só energia RMS."""
    from retranscritor import retranscrever

    pasta_tr = tmp_path / "tr"
    pasta_tr.mkdir()
    loop = _escrever_wav(tmp_path / "lb.wav", segundos=1.0, freq=440.0)
    mic = _escrever_wav(tmp_path / "mic.wav", segundos=1.0, freq=880.0)

    modelo_lb = _modelo_com([("reuniao geral do projeto", 0.0, 0.5)])
    modelo_mic = _modelo_com([("minha frase exclusiva do microfone", 0.0, 0.5)])

    def _transcribe_por_arquivo(pedaco, **kwargs):
        raise AssertionError("roteador de modelo deve ser por fonte")

    # Roteia por tamanho de bloco não é viável; em vez disso o retranscritor
    # deve chamar transcrever_fonte por fonte — aqui validamos a integração
    # via monkeypatch em audio_fontes.transcrever_fonte.
    import retranscritor

    chamadas = []

    def _fake_transcrever_fonte(path, source, *, model, **_kwargs):
        chamadas.append(source)
        if source == AudioSource.MICROPHONE:
            return [
                SegmentoSTT("m1", 0, 500, source, "minha frase exclusiva do microfone", False)
            ]
        return [SegmentoSTT("l1", 0, 500, source, "reuniao geral do projeto", False)]

    import audio_fontes

    orig = audio_fontes.transcrever_fonte
    audio_fontes.transcrever_fonte = _fake_transcrever_fonte
    try:
        saida = retranscrever(
            str(loop),
            pasta_saida=str(pasta_tr),
            nome_base_saida="c2-mic-exclusivo",
            modelo_whisper=modelo_lb,
            diarizar=False,
            caminho_mic=str(mic),
        )
    finally:
        audio_fontes.transcrever_fonte = orig
    texto = Path(saida).read_text(encoding="utf-8").lower()
    assert "minha frase exclusiva do microfone" in texto
    assert AudioSource.MICROPHONE in chamadas


def test_mic_cifrado_aceito(chave_teste, tmp_path):
    """Leitor de mic aceita WAV cifrado (sem wave.open sobre ciphertext)."""
    from crypto_storage import criptografar_wav

    mic = _escrever_wav(tmp_path / "mic.wav", segundos=0.5)
    enc = criptografar_wav(str(mic))
    assert enc.endswith(".wav.enc")

    info = inspect_audio(Path(enc), AudioSource.MICROPHONE)
    assert info.sample_rate == 16000
    blocos = list(iter_audio(Path(enc), AudioSource.MICROPHONE))
    assert blocos and blocos[0].samples.size > 0

    modelo = _modelo_com([("fala cifrada do mic", 0.0, 0.4)])
    segs = transcrever_fonte(Path(enc), AudioSource.MICROPHONE, model=modelo)
    assert any("fala cifrada do mic" in s.text for s in segs)


def test_eco_nao_duplica_frase():
    """Eco confirmado (mesmo texto + sobreposição temporal) sai uma vez só."""
    lb = [SegmentoSTT("l1", 0, 1000, AudioSource.LOOPBACK, "vamos revisar o cronograma", False)]
    mic = [SegmentoSTT("m1", 200, 1200, AudioSource.MICROPHONE, "vamos revisar o cronograma", False)]
    fundidos = mesclar_segmentos(lb, mic)
    assert len(fundidos) == 1
    assert "cronograma" in fundidos[0].text


def test_falas_simultaneas_preservadas():
    """Falas simultâneas independentes permanecem, marcadas com overlap."""
    lb = [SegmentoSTT("l1", 0, 1000, AudioSource.LOOPBACK, "relatorio final na sexta", False)]
    mic = [SegmentoSTT("m1", 200, 1200, AudioSource.MICROPHONE, "minha duvida sobre o contrato", False)]
    fundidos = mesclar_segmentos(lb, mic)
    assert len(fundidos) == 2
    textos = " ".join(s.text for s in fundidos)
    assert "relatorio" in textos and "contrato" in textos
    assert any(s.overlap for s in fundidos)


def test_offset_de_inicio_alinha_fontes():
    """Fusão usa origem temporal explícita: ordem cronológica entre fontes."""
    lb = [SegmentoSTT("l1", 5000, 5500, AudioSource.LOOPBACK, "fala tardia do loopback", False)]
    mic = [SegmentoSTT("m1", 500, 1000, AudioSource.MICROPHONE, "fala inicial do mic", False)]
    fundidos = mesclar_segmentos(lb, mic)
    assert [s.segment_id for s in fundidos] == ["m1", "l1"]
    assert fundidos[0].start_ms < fundidos[1].start_ms


def test_formato_nao_implementado_rejeitado(tmp_path):
    """PCM fora de 16/24/32 é rejeitado explicitamente, sem fallback uint8."""
    caminho = tmp_path / "a8.wav"
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(16000)
        w.writeframes(bytes([128] * 1600))
    try:
        inspect_audio(caminho, AudioSource.LOOPBACK)
    except UnsupportedAudioFormat:
        return
    raise AssertionError("PCM 8-bit deveria levantar UnsupportedAudioFormat")


@pytest.mark.parametrize("protegido", [False, True])
def test_diarizacao_usa_audio_da_origem_de_cada_fala(tmp_path, monkeypatch, chave_teste, protegido):
    """O embedding de uma fala do mic não pode vir do loopback simultâneo."""
    import audio_fontes
    import diarizador
    import retranscritor
    from politica_privacidade import ProtectionMode

    loop = tmp_path / "lb.wav"
    mic = tmp_path / "mic.wav"
    for caminho, amplitude in ((loop, 5000), (mic, -5000)):
        with wave.open(str(caminho), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(np.full(16000 * 2, amplitude, dtype="<i2").tobytes())

    def transcrever(_path, source, **_kwargs):
        return [SegmentoSTT(source.value, 0, 2000, source,
                            "fala local" if source == AudioSource.MICROPHONE else "fala remota", False)]

    medias = []
    referencias_loopback = []

    def diarizar(trechos_audio, segmentos, **_kwargs):
        medias.extend(float(np.mean(t)) for t in trechos_audio)
        referencias_loopback.extend(float(np.mean(t)) for t in _kwargs["trechos_loopback"])
        return ([(f"FALANTE_{i:02d}", s, e, texto)
                 for i, (s, e, texto) in enumerate(segmentos)], {})

    monkeypatch.setattr(audio_fontes, "transcrever_fonte", transcrever)
    monkeypatch.setattr(diarizador, "diarizar", diarizar)
    monkeypatch.setattr("politica_privacidade.modo_efetivo", lambda: (
        ProtectionMode.PROTECTED if protegido else ProtectionMode.COMPATIBLE
    ))

    resultado = retranscritor.retranscrever_resultado(
        str(loop), caminho_mic=str(mic), pasta_saida=str(tmp_path / "saida"),
        nome_base_saida="origens", modelo_whisper=object(),
        diarizar=True, identificar_voz=False, usar_vozes_conhecidas=False,
    )

    assert len(resultado.segmentos) == 2
    assert medias[0] > 0.1
    assert medias[1] < -0.1
    assert referencias_loopback == pytest.approx([medias[0], medias[0]], abs=0.001)
