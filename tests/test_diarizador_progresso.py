# -*- coding: utf-8 -*-
"""Testes de progresso da diarização (Fase 3 — FR-3.5)."""
import numpy as np
from unittest.mock import MagicMock

from diarizador import diarizar, mensagem_progresso_segmentos


def test_mensagem_progresso_formato():
    assert mensagem_progresso_segmentos(10, 45) == "10/45 segmentos..."


def test_progresso_a_cada_10_segmentos(monkeypatch):
    monkeypatch.setattr("diarizador._carregar_encoder", lambda: MagicMock())
    monkeypatch.setattr("diarizador._extrair_embedding", lambda _e, _t: np.ones(192, dtype=np.float32))

    n = 25
    trechos = [np.ones(16000, dtype=np.float32) for _ in range(n)]
    segmentos = [(float(i), float(i + 1), f"seg{i}") for i in range(n)]
    chamadas = []

    diarizar(trechos, segmentos, on_status=chamadas.append)

    progresso = [c for c in chamadas if "segmentos..." in c and "/" in c]
    assert "10/25 segmentos..." in progresso
    assert "20/25 segmentos..." in progresso
    assert "25/25 segmentos..." in progresso