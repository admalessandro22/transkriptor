# -*- coding: utf-8 -*-
"""Testes do correlacionador Meet (Fase 8 — FR-8.3/8.4)."""
import numpy as np

from correlacionador import (
    aplicar_nomes_meet,
    correlacionar_segmento,
    mesclar_prioridade_rotulos,
)
from identificador_voz import salvar_voz_conhecida, carregar_vozes_conhecidas, renomear_falante


def test_correlacionar_segmento_ana_em_10_5s():
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    nome = correlacionar_segmento(10.0, 12.0, eventos, janela_margem=1.5)
    assert nome == "Ana Silva"


def test_correlacionar_segmento_fora_da_janela_retorna_none():
    eventos = [{"nome": "Ana", "ts_sec": 20.0, "tipo": "ativo"}]
    assert correlacionar_segmento(10.0, 12.0, eventos, janela_margem=1.5) is None


def test_correlacionar_voto_por_frequencia():
    eventos = [
        {"nome": "Ana", "ts_sec": 10.2, "tipo": "ativo"},
        {"nome": "Ana", "ts_sec": 10.8, "tipo": "ativo"},
        {"nome": "Bob", "ts_sec": 11.0, "tipo": "ativo"},
    ]
    assert correlacionar_segmento(10.0, 12.0, eventos) == "Ana"


def test_aplicar_nomes_meet_substitui_falante():
    resultado = [("FALANTE_00", 10.0, 12.0, "ola")]
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    rotulado = aplicar_nomes_meet(resultado, eventos)
    assert rotulado[0][0] == "Ana Silva"


def test_aplicar_nomes_meet_nao_substitui_voce():
    resultado = [("VOCÊ", 10.0, 12.0, "eu falo")]
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    rotulado = aplicar_nomes_meet(resultado, eventos, sobrescrever_voce=False)
    assert rotulado[0][0] == "VOCÊ"


def test_mesclar_prioridade_meet_sobre_voce():
    resultado = [("VOCÊ", 10.0, 12.0, "texto")]
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    mesclado = mesclar_prioridade_rotulos(resultado, eventos, vozes_conhecidas={})
    assert mesclado[0][0] == "Ana Silva"


def test_aplicar_nomes_meet_substitui_voz_conhecida():
    resultado = [("Carlos", 10.0, 12.0, "ola")]
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    rotulado = aplicar_nomes_meet(resultado, eventos)
    assert rotulado[0][0] == "Ana Silva"


def test_mesclar_prioridade_meet_sobre_voz_conhecida():
    """Meet deve vencer nome persistido (Carlos) na mesma janela temporal."""
    resultado = [("Carlos", 10.0, 12.0, "ola")]
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    vozes = {
        "Carlos": {
            "rotulo_origem": "FALANTE_01",
            "embedding": [1.0, 0.0, 0.2],
        }
    }
    centroides = {"FALANTE_01": np.array([1.0, 0.0, 0.2], dtype=np.float32)}
    mesclado = mesclar_prioridade_rotulos(
        resultado,
        eventos,
        vozes_conhecidas=vozes,
        centroides_por_rotulo=centroides,
    )
    assert mesclado[0][0] == "Ana Silva"


def test_renomear_falante_persiste_voz_conhecida(tmp_path):
    emb = np.array([1.0, 0.0, 0.2], dtype=np.float32)
    arquivo = tmp_path / "vozes_conhecidas.json"
    renomear_falante("FALANTE_01", "Carlos", emb, arquivo)
    vozes = carregar_vozes_conhecidas(arquivo)
    assert "Carlos" in vozes
    assert vozes["Carlos"]["rotulo_origem"] == "FALANTE_01"
    assert np.allclose(vozes["Carlos"]["embedding"], emb)