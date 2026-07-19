# -*- coding: utf-8 -*-
"""Testes do watchdog de threads (NFR-1, FR-6.1, FR-6.2)."""
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from watchdog import Watchdog
from transcricao_core import Transcritor


class _TranscritorFake:
    def __init__(self, cap_viva=True, proc_viva=True):
        self.rodando = True
        self._thread_cap = MagicMock()
        self._thread_cap.is_alive = MagicMock(return_value=cap_viva)
        self._thread_proc = MagicMock()
        self._thread_proc.is_alive = MagicMock(return_value=proc_viva)
        self._reiniciar_captura = MagicMock()
        self._reiniciar_processar = MagicMock()


def test_watchdog_reinicia_captura_morta():
    t = _TranscritorFake(cap_viva=False, proc_viva=True)
    status_msgs = []
    w = Watchdog(t, on_status=status_msgs.append, intervalo=0.05)
    w._verificar()
    t._reiniciar_captura.assert_called_once()
    assert any("captura" in m for m in status_msgs)


def test_watchdog_reinicia_processamento_morto():
    t = _TranscritorFake(cap_viva=True, proc_viva=False)
    status_msgs = []
    w = Watchdog(t, on_status=status_msgs.append, intervalo=0.05)
    w._verificar()
    t._reiniciar_processar.assert_called_once()
    assert any("processamento" in m for m in status_msgs)


def test_watchdog_erro_critico_apos_limite_reinicios(monkeypatch):
    monkeypatch.setattr("watchdog.LIMITE_REINICIOS", 2)
    t = _TranscritorFake(cap_viva=False, proc_viva=True)
    erros = []
    w = Watchdog(t, on_erro_critico=erros.append, intervalo=0.05)
    w._verificar()
    w._verificar()
    w._verificar()
    assert len(erros) == 1
    # FR-6.2: mensagem específica de falha de captura
    assert "Sem áudio do sistema" in erros[0]
    assert "dispositivo de saída" in erros[0]


def test_watchdog_toast_apos_3_falhas_captura():
    """FR-6.2: três falhas consecutivas de captura → toast específico."""
    t = _TranscritorFake(cap_viva=False, proc_viva=True)
    erros = []
    w = Watchdog(t, on_erro_critico=erros.append, intervalo=0.05)
    # LIMITE_REINICIOS=3 → 3 reinícios + 1 crítico
    for _ in range(4):
        w._verificar()
    assert len(erros) == 1
    assert erros[0] == "Sem áudio do sistema — verifique o dispositivo de saída"


def test_watchdog_loop_para_quando_stop():
    t = _TranscritorFake()
    w = Watchdog(t, intervalo=0.05)
    w.start()
    time.sleep(0.15)
    w.stop()
    assert not w._thread.is_alive()


def test_reiniciar_processar_somente_audio_continua_gravando_wav(tmp_path, monkeypatch):
    """FR-2.4×FR-6.1: em modo somente áudio, restart deve usar _processar_somente_audio."""
    import wave

    pasta_audio = tmp_path / "audio"
    monkeypatch.setattr("transcricao_core.PASTA_AUDIO", str(pasta_audio))
    monkeypatch.setattr("crypto_storage.criptografia_ativa", lambda: False)

    t = Transcritor(
        pasta_saida=str(tmp_path),
        diarizar_ao_final=False,
        capturar_mic=False,
        criptografar=False,
        chunk=0.05,
    )
    t._abrir_arquivo()
    t.rodando = True
    t._stop.clear()
    t._somente_audio = True
    t._modelo = None

    # Simula morte da thread de somente-áudio
    t._thread_proc = threading.Thread(target=lambda: None, daemon=True)
    t._thread_proc.start()
    t._thread_proc.join(timeout=1)

    t._reiniciar_processar()
    assert t._thread_proc is not None
    assert t._thread_proc.is_alive()

    # Enfileira frames e aguarda gravação no WAV
    audio = np.full(int(16000 * 0.2), 0.3, dtype=np.float32)
    t._q.put(audio)
    deadline = time.time() + 3
    while time.time() < deadline:
        if t._wav is not None:
            # frames ainda no handle aberto
            try:
                # Wave_write não expõe nframes facilmente; checamos tamanho do arquivo temp
                if Path(t._caminho_wav).stat().st_size > 44:
                    break
            except Exception:
                pass
        time.sleep(0.05)

    t.stop()
    wavs = list(pasta_audio.glob("*_audio.wav"))
    assert len(wavs) == 1, f"esperado WAV em {pasta_audio}: {list(pasta_audio.iterdir()) if pasta_audio.exists() else None}"
    with wave.open(str(wavs[0]), "rb") as w:
        assert w.getnframes() > 0


def test_reiniciar_processar_preserva_arquivo_e_continua_escrevendo(tmp_path):
    """FR-6.1: matar processar, reiniciar e provar que o texto continua no arquivo."""
    t = Transcritor(
        pasta_saida=str(tmp_path),
        diarizar_ao_final=False,
        capturar_mic=False,
        criptografar=False,
        chunk=0.05,
    )
    t._abrir_arquivo()
    caminho = t._caminho_saida
    t.rodando = True
    t._stop.clear()
    t._modelo = MagicMock()

    chamadas = {"n": 0}

    def _transcrever_flaky(audio, final=False):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            if t._arq:
                t._arq.write("[00:00:01] primeiro\n")
                t._arq.flush()
            raise RuntimeError("excecao injetada para matar processar")
        if t._arq:
            t._arq.write("[00:00:02] segundo\n")
            t._arq.flush()

    t._transcrever_bloco = _transcrever_flaky
    audio = np.zeros(int(16000 * 0.05), dtype=np.float32)

    t._thread_proc = threading.Thread(target=t._processar, daemon=True)
    t._thread_proc.start()
    t._q.put(audio)
    t._thread_proc.join(timeout=3)
    assert not t._thread_proc.is_alive()

    # Arquivos devem permanecer abertos após morte sem stop()
    assert t._arq is not None
    assert t._wav is not None

    t._reiniciar_processar()
    assert t._thread_proc is not None
    t._q.put(audio)
    # aguarda o segundo bloco
    deadline = time.time() + 3
    while chamadas["n"] < 2 and time.time() < deadline:
        time.sleep(0.05)
    assert chamadas["n"] >= 2

    t.stop()
    conteudo = Path(caminho).read_text(encoding="utf-8")
    assert "primeiro" in conteudo
    assert "segundo" in conteudo
