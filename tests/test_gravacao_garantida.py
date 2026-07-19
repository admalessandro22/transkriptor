# -*- coding: utf-8 -*-
"""T-F2-01+ — gravação local garantida do áudio da reunião (FR-2.1, FR-2.8)."""
import shutil
import threading
import time
import wave
from collections import namedtuple
from pathlib import Path
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
    monkeypatch.setattr("crypto_storage.criptografia_ativa", lambda: False)

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
    monkeypatch.setattr("crypto_storage.criptografia_ativa", lambda: False)

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


def test_criptografar_wav_gera_enc_e_remove_plaintext(chave_teste, tmp_path):
    """FR-2.2 / SEC-2.1: criptografar_wav produz .wav.enc legível via ler_bytes_arquivo."""
    from crypto_storage import criptografar_wav, ler_bytes_arquivo

    wav = tmp_path / "reuniao_audio.wav"
    conteudo = b"RIFF" + b"\x00" * 40 + b"dados-audio-fake"
    wav.write_bytes(conteudo)

    enc = criptografar_wav(str(wav))
    assert enc.endswith(".wav.enc")
    assert Path(enc).is_file()
    assert not wav.exists()
    assert ler_bytes_arquivo(enc) == conteudo


def test_criptografar_wav_noop_sem_criptografia(tmp_path, monkeypatch):
    from crypto_storage import criptografar_wav

    monkeypatch.setattr("crypto_storage.criptografia_ativa", lambda: False)
    wav = tmp_path / "x_audio.wav"
    wav.write_bytes(b"plain")
    out = criptografar_wav(str(wav))
    assert out == str(wav)
    assert wav.exists()


def test_preservar_audio_com_criptografia_ativa(chave_teste, tmp_path, monkeypatch):
    """Após stop com cripto, só .wav.enc em PASTA_AUDIO."""
    from crypto_storage import ler_bytes_arquivo

    pasta_audio = tmp_path / "audio"
    monkeypatch.setattr("transcricao_core.PASTA_AUDIO", str(pasta_audio))
    monkeypatch.setattr("crypto_storage.criptografia_ativa", lambda: True)

    t = Transcritor(
        pasta_saida=str(tmp_path),
        diarizar_ao_final=False,
        capturar_mic=False,
        criptografar=True,
    )
    t._abrir_arquivo()
    audio = np.full(4000, 0.1, dtype=np.float32)
    t._modelo = MagicMock()
    t._modelo.transcribe.return_value = ([], MagicMock())
    t._transcrever_bloco(audio)
    t.rodando = True
    t._thread_cap = threading.Thread(target=lambda: None, daemon=True)
    t._thread_proc = threading.Thread(target=lambda: None, daemon=True)
    t.stop()

    encs = list(pasta_audio.glob("*.wav.enc"))
    plains = list(pasta_audio.glob("*.wav"))
    assert len(encs) == 1
    assert plains == []
    plano = ler_bytes_arquivo(str(encs[0]))
    assert len(plano) > 44  # cabeçalho WAV + frames


def test_recuperar_orfaos_wav_no_start(chave_teste, tmp_path):
    from crypto_storage import recuperar_orfaos_wav, ler_bytes_arquivo

    pasta = tmp_path / "audio"
    pasta.mkdir()
    orfao = pasta / "crash_audio.wav"
    dados = b"RIFF" + b"\x01" * 100
    orfao.write_bytes(dados)

    n = recuperar_orfaos_wav(str(pasta))
    assert n == 1
    assert not orfao.exists()
    enc = pasta / "crash_audio.wav.enc"
    assert enc.is_file()
    assert ler_bytes_arquivo(str(enc)) == dados


def test_api_transcricoes_nao_lista_audio(tmp_path, monkeypatch, headers_token):
    """SEC-2.1: /api/transcricoes não lista arquivos de audio/."""
    from assistente import app

    pasta = tmp_path / "transcricoes"
    audio = pasta / "audio"
    pasta.mkdir()
    audio.mkdir()
    (pasta / "ok.txt").write_text("ola", encoding="utf-8")
    (audio / "segredo_audio.wav").write_bytes(b"x")
    (audio / "segredo.wav.enc").write_bytes(b"y")
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(pasta))

    client = app.test_client()
    r = client.get("/api/transcricoes", headers=headers_token)
    assert r.status_code == 200
    nomes = [i["arquivo"] for i in r.get_json()]
    assert "ok.txt" in nomes
    assert not any("audio" in n or n.endswith(".wav") or n.endswith(".wav.enc") for n in nomes)
    # path traversal / subdir
    assert caminho_nao_serve_audio(client, headers_token, "audio/segredo_audio.wav")


def caminho_nao_serve_audio(client, headers, nome):
    from assistente import caminho_transcricao_seguro

    return caminho_transcricao_seguro(nome) is None
