# -*- coding: utf-8 -*-
"""Regressões finais T-10.H1 (privacidade, nomes e ciclo pós-reunião)."""
from __future__ import annotations

import threading
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import numpy as np

import retranscritor
from crypto_storage import caminho_transcricao_novo, criptografar_wav
from diarizacao_final import preservar_audios
from fila_processamento import FilaProcessamento


def test_consentimento_tardio_respeita_pausa(modulo_transkriptor, monkeypatch):
    """FR-10.B1/FR-10.A4: pausar revoga captura ainda não iniciada."""
    app = modulo_transkriptor.AppTranskriptor.__new__(
        modulo_transkriptor.AppTranskriptor
    )
    app._lock = threading.Lock()
    app._consentimento_em_andamento = True
    app._recusa_reuniao_ativa = False
    app.deteccao_ativa = False
    app.detector = SimpleNamespace(reuniao_ativa=True)
    app._pedir_consentimento = lambda: True
    app._status = lambda _msg: None
    app._iniciar_transcricao = MagicMock()

    app._pedir_e_iniciar()

    app._iniciar_transcricao.assert_not_called()


def test_audio_enc_nao_cria_wav_plaintext_temporario(chave_teste, tmp_path, monkeypatch):
    """SEC-10.F4: leitura criptografada não deixa WAV em TEMP após interrupção."""
    pasta_audio = tmp_path / "audio"
    pasta_audio.mkdir()
    wav = pasta_audio / "reuniao_audio.wav"
    with wave.open(str(wav), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(16000)
        arquivo.writeframes((np.zeros(1600, dtype=np.int16)).tobytes())
    enc = criptografar_wav(str(wav))
    assert Path(enc).is_file()

    original_mkstemp = retranscritor.tempfile.mkstemp

    def mkstemp_nunca_para_wav(*args, **kwargs):
        if kwargs.get("suffix") == ".wav":
            raise AssertionError("não deve criar WAV plaintext temporário")
        return original_mkstemp(*args, **kwargs)

    monkeypatch.setattr(retranscritor.tempfile, "mkstemp", mkstemp_nunca_para_wav)
    audio, sr = retranscritor._ler_audio_pcm(enc)

    assert sr == 16000
    assert audio.size > 0
    assert not list(tmp_path.glob("**/*.wav"))


def test_nova_reuniao_no_mesmo_minuto_recebe_nome_livre(tmp_path, monkeypatch):
    """FR-10.E1: uma nova captura nunca reutiliza áudio/TXT existente."""
    import crypto_storage

    monkeypatch.setattr(
        crypto_storage,
        "nome_base_transcricao",
        lambda *_, **__: "transcricao_2026-08-06_10h00",
    )
    (tmp_path / "transcricao_2026-08-06_10h00.txt").write_text("anterior")
    (tmp_path / "transcricao_2026-08-06_10h00_audio.wav").write_bytes(b"RIFF")

    novo = Path(caminho_transcricao_novo(str(tmp_path), criptografar=False))

    assert novo.name == "transcricao_2026-08-06_10h00_02.txt"


def test_preservacao_nao_apaga_audio_com_mesmo_nome(tmp_path):
    """FR-10.G1: colisão de retenção preserva os dois arquivos."""
    pasta_audio = tmp_path / "audio"
    pasta_audio.mkdir()
    existente = pasta_audio / "reuniao_audio.wav"
    existente.write_bytes(b"RIFF anterior")
    origem = tmp_path / "reuniao_audio.wav"
    origem.write_bytes(b"RIFF nova")

    destinos = preservar_audios(False, str(origem), pasta_audio=str(pasta_audio))

    assert existente.read_bytes() == b"RIFF anterior"
    assert len(destinos) == 1
    assert Path(destinos[0]).name == "reuniao_audio_02.wav"
    assert Path(destinos[0]).read_bytes() == b"RIFF nova"


def test_worker_falho_marcado_avanca_para_proximo_job(tmp_path):
    """FR-10.D2: falha terminal não bloqueia jobs pendentes seguintes."""
    from app_processamento import ProcessamentoReuniaoMixin

    pasta = tmp_path / "transcricoes"
    audio_dir = pasta / "audio"
    audio_dir.mkdir(parents=True)
    fila = FilaProcessamento(str(pasta))
    audio = audio_dir / "reuniao.wav"
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    primeiro = fila.enfileirar(str(audio), None, "primeiro", {})
    segundo = fila.enfileirar(str(audio), None, "segundo", {})
    fila.reivindicar(primeiro)
    fila.falhar(primeiro, "runtimeerror")

    app = ProcessamentoReuniaoMixin.__new__(ProcessamentoReuniaoMixin)
    app._lock = threading.Lock()
    app.fila = fila
    app._worker_processamento = SimpleNamespace()
    app._estado_processamento = "Processando"
    app._ultimo_job_id = primeiro
    app._atualizar_tooltip = lambda: None
    app._despachar_proximo_job = MagicMock()
    app._aguardar_worker(primeiro, SimpleNamespace(wait=lambda: 1))

    app._despachar_proximo_job.assert_called_once_with()
    assert fila.obter(segundo).estado == "pending"
