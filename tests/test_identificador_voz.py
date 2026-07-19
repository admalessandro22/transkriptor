# -*- coding: utf-8 -*-
"""Testes do módulo identificador_voz (Fase 7 — FR-7.1/7.2)."""
import numpy as np
import pytest

from identificador_voz import (
    carregar_perfil,
    identificar_cluster,
    media_embeddings,
    salvar_perfil,
    similaridade_cosseno,
)


def test_salvar_carregar_roundtrip(tmp_path):
    emb = np.array([1.0, 0.0, 0.5], dtype=np.float32)
    caminho = tmp_path / "perfil_usuario.npz"
    salvar_perfil(emb, caminho)
    carregado = carregar_perfil(caminho)
    assert carregado is not None
    assert np.allclose(carregado, emb)


def test_carregar_perfil_inexistente_retorna_none(tmp_path):
    assert carregar_perfil(tmp_path / "ausente.npz") is None


def test_identificar_cluster_mais_similar():
    perfil = np.array([1.0, 0.0], dtype=np.float32)
    centroides = [
        np.array([0.0, 1.0], dtype=np.float32),
        np.array([0.95, 0.05], dtype=np.float32),
    ]
    assert identificar_cluster(centroides, perfil, limiar=0.72) == 1


def test_identificar_cluster_abaixo_limiar_retorna_none():
    perfil = np.array([1.0, 0.0], dtype=np.float32)
    centroides = [np.array([0.0, 1.0], dtype=np.float32)]
    assert identificar_cluster(centroides, perfil, limiar=0.72) is None


def test_similaridade_cosseno_identicos():
    v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert similaridade_cosseno(v, v) == pytest.approx(1.0, abs=1e-5)


def test_media_embeddings():
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0], dtype=np.float32)
    m = media_embeddings([a, b])
    assert np.allclose(m, [0.5, 0.5])