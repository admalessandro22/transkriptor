# -*- coding: utf-8 -*-
"""Testes de resolução DEVICE_WHISPER (Fase 2 — FR-2.3/2.4)."""
from unittest.mock import MagicMock, patch

from config import DEVICE_WHISPER, resolver_device_whisper


def test_auto_usa_cpu_sem_cuda(monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert resolver_device_whisper("auto") == "cpu"


def test_auto_usa_cuda_com_gpu(monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert resolver_device_whisper("auto") == "cuda"


def test_valor_explicito_nao_alterado():
    assert resolver_device_whisper("cpu") == "cpu"
    assert resolver_device_whisper("cuda") == "cuda"


def test_device_whisper_default_auto():
    assert DEVICE_WHISPER == "auto"


def test_transcritor_carrega_modelo_com_device_resolvido(monkeypatch):
    monkeypatch.setattr("transcricao_core.resolver_device_whisper", lambda _: "cpu")
    from transcricao_core import Transcritor

    t = Transcritor(diarizar_ao_final=False)
    mock_model = MagicMock()
    with patch("transcricao_core.WhisperModel", return_value=mock_model) as wm:
        t._carregar_modelo()
        wm.assert_called_once()
        assert wm.call_args.kwargs["device"] == "cpu"
    assert t._modelo is mock_model