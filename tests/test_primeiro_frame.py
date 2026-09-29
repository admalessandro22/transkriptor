# -*- coding: utf-8 -*-
"""T-15.A2 — o instante zero é o primeiro frame capturado, não o fim do start()."""
from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np

from config import SAMPLE_RATE
from transcricao_core import Transcritor


def _transcritor(tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), capturar_mic=False, processar_ao_vivo=True)
    t.rodando = True
    return t


def test_primeiro_frame_desconta_duracao_do_bloco(tmp_path):
    """record() devolve 1 s de áudio: o 1º frame aconteceu ~1 s antes do retorno."""
    t = _transcritor(tmp_path)
    assert t.primeiro_frame_monotonic_ns is None
    antes = time.monotonic_ns()
    t._enfileirar_audio(np.zeros(SAMPLE_RATE, dtype=np.float32))
    depois = time.monotonic_ns()
    marcado = t.primeiro_frame_monotonic_ns
    assert antes - 1_000_000_000 <= marcado <= depois - 1_000_000_000


def test_primeiro_frame_nao_se_move(tmp_path):
    t = _transcritor(tmp_path)
    t._enfileirar_audio(np.zeros(SAMPLE_RATE // 2, dtype=np.float32))
    primeiro = t.primeiro_frame_monotonic_ns
    t._enfileirar_audio(np.zeros(SAMPLE_RATE, dtype=np.float32))
    assert t.primeiro_frame_monotonic_ns == primeiro


def test_mic_nao_define_instante_zero(tmp_path):
    """O tempo dos segmentos é o do loopback; o mic não move o zero."""
    t = _transcritor(tmp_path)
    t._registrar_frames_captura("microfone", SAMPLE_RATE)
    assert t.primeiro_frame_monotonic_ns is None


def test_reinicio_das_metricas_zera_instante(tmp_path):
    t = _transcritor(tmp_path)
    t._enfileirar_audio(np.zeros(SAMPLE_RATE, dtype=np.float32))
    t._resetar_metricas_captura()
    assert t.primeiro_frame_monotonic_ns is None


def test_snapshot_do_job_prefere_primeiro_frame_real():
    from app_processamento import primeiro_frame_do_job

    sessao = SimpleNamespace(first_frame_monotonic_ns=5_000)
    assert primeiro_frame_do_job(sessao, SimpleNamespace(primeiro_frame_monotonic_ns=4_000)) == 4_000
    assert primeiro_frame_do_job(sessao, SimpleNamespace(primeiro_frame_monotonic_ns=None)) == 5_000
    assert primeiro_frame_do_job(sessao, None) == 5_000
