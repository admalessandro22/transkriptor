# -*- coding: utf-8 -*-
"""Testes do fluxo renomear falante (Fase 8 — FR-8.5)."""
import numpy as np

from identificador_voz import carregar_vozes_conhecidas
from renomear_falante_flow import (
    embedding_para_rotulo,
    persistir_renomeacao_falante,
    rotulos_falante_disponiveis,
)


def test_rotulos_falante_disponiveis():
    centroides = {
        "FALANTE_01": np.array([1.0, 0.0], dtype=np.float32),
        "FALANTE_00": np.array([0.0, 1.0], dtype=np.float32),
        "VOCÊ": np.array([0.5, 0.5], dtype=np.float32),
    }
    assert rotulos_falante_disponiveis(centroides) == ["FALANTE_00", "FALANTE_01"]


def test_persistir_renomeacao_falante(tmp_path):
    emb = np.array([1.0, 0.0, 0.2], dtype=np.float32)
    centroides = {"FALANTE_01": emb}
    arquivo = tmp_path / "vozes_conhecidas.json"
    nome = persistir_renomeacao_falante("FALANTE_01", "Carlos", centroides, arquivo)
    assert nome == "Carlos"
    vozes = carregar_vozes_conhecidas(arquivo)
    assert "Carlos" in vozes
    assert np.allclose(vozes["Carlos"]["embedding"], emb)


def test_persistir_renomeacao_rejeita_rotulo_invalido(tmp_path):
    centroides = {"FALANTE_00": np.array([1.0], dtype=np.float32)}
    try:
        persistir_renomeacao_falante("Ana", "X", centroides, tmp_path / "v.json")
        assert False, "deveria levantar ValueError"
    except ValueError:
        pass


def test_embedding_para_rotulo_normaliza_maiusculas():
    emb = np.array([0.1, 0.2], dtype=np.float32)
    got = embedding_para_rotulo({"FALANTE_02": emb}, "falante_02")
    assert np.allclose(got, emb)