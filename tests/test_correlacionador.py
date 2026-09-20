# -*- coding: utf-8 -*-
"""Testes do correlacionador Meet (FR-5.2/FR-5.3 e legado)."""
import numpy as np
import pytest

from correlacionador import (
    aplicar_nomes_meet,
    correlacionar_por_legenda,
    correlacionar_segmento,
    mesclar_prioridade_rotulos,
    similaridade_tokens,
)
from identificador_voz import carregar_vozes_conhecidas, renomear_falante


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


def test_aplicar_nomes_meet_preserva_falante_sem_confirmacao():
    """FR-13.D6: evento 'ativo' sozinho nunca confirma nome."""
    resultado = [("FALANTE_00", 10.0, 12.0, "ola")]
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    rotulado = aplicar_nomes_meet(resultado, eventos)
    assert rotulado[0][0] == "FALANTE_00"


def test_aplicar_nomes_meet_nao_substitui_voce():
    resultado = [("VOCÊ", 10.0, 12.0, "eu falo")]
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    rotulado = aplicar_nomes_meet(resultado, eventos, sobrescrever_voce=False)
    assert rotulado[0][0] == "VOCÊ"


def test_mesclar_prioridade_preserva_voce_sem_confirmacao():
    """FR-13.D6: sem confirmação manual, VOCÊ prevalece sobre palpite."""
    resultado = [("VOCÊ", 10.0, 12.0, "texto")]
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    mesclado = mesclar_prioridade_rotulos(resultado, eventos, vozes_conhecidas={})
    assert mesclado[0][0] == "VOCÊ"


def test_aplicar_nomes_meet_preserva_voz_conhecida():
    """FR-13.D6: nome de voz persistida não cai por palpite de tile."""
    resultado = [("Carlos", 10.0, 12.0, "ola")]
    eventos = [{"nome": "Ana Silva", "ts_sec": 10.5, "tipo": "ativo"}]
    rotulado = aplicar_nomes_meet(resultado, eventos)
    assert rotulado[0][0] == "Carlos"


def test_mesclar_prioridade_preserva_voz_conhecida():
    """FR-13.D6: confirmação ausente mantém o nome persistido (Carlos)."""
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
    assert mesclado[0][0] == "Carlos"


def test_renomear_falante_persiste_voz_conhecida(tmp_path):
    emb = np.array([1.0, 0.0, 0.2], dtype=np.float32)
    arquivo = tmp_path / "vozes_conhecidas.json"
    renomear_falante("FALANTE_01", "Carlos", emb, arquivo)
    vozes = carregar_vozes_conhecidas(arquivo)
    assert "Carlos" in vozes
    assert vozes["Carlos"]["rotulo_origem"] == "FALANTE_01"
    assert np.allclose(vozes["Carlos"]["embedding"], emb)


def test_similaridade_tokens_jaccard():
    """FR-5.2: similaridade_tokens usa Jaccard em minúsculas."""
    assert similaridade_tokens("Bom dia a todos", "bom dia a todos") == pytest.approx(1.0)
    # 2 em comum (ola, mundo) de 3 união → 2/3
    assert similaridade_tokens("ola mundo", "ola mundo cruel") == pytest.approx(2 / 3)
    assert similaridade_tokens("aaa", "bbb") == 0.0
    assert similaridade_tokens("", "texto") == 0.0


def test_correlacionar_por_legenda_escolhe_pelo_texto():
    """FR-5.2: dois falantes na mesma janela — nome pelo texto da legenda."""
    eventos = [
        {
            "nome": "Ana",
            "ts_sec": 10.2,
            "tipo": "legenda",
            "texto": "vamos fechar o orcamento hoje",
        },
        {
            "nome": "Bruno",
            "ts_sec": 10.8,
            "tipo": "legenda",
            "texto": "preciso de mais prazo no projeto",
        },
        # falante ativo mais frequente seria Bruno se só contasse votos
        {"nome": "Bruno", "ts_sec": 10.5, "tipo": "ativo"},
        {"nome": "Bruno", "ts_sec": 11.0, "tipo": "ativo"},
    ]
    assert (
        correlacionar_por_legenda(
            10.0, 12.0, "vamos fechar o orcamento hoje por favor", eventos
        )
        == "Ana"
    )
    assert (
        correlacionar_por_legenda(
            10.0, 12.0, "preciso de mais prazo no projeto urgente", eventos
        )
        == "Bruno"
    )


def test_correlacionar_por_legenda_abaixo_do_limiar_retorna_none():
    eventos = [
        {"nome": "Ana", "ts_sec": 10.5, "tipo": "legenda", "texto": "alfa beta gama"},
    ]
    assert correlacionar_por_legenda(10.0, 12.0, "xyz completamente diferente", eventos) is None


def test_aplicar_nomes_meet_sugestao_nao_autoaplica():
    """FR-13.D6: legenda forte vira sugestão (D7), não rótulo automático."""
    resultado = [
        ("FALANTE_00", 10.0, 12.0, "vamos fechar o orcamento hoje"),
        ("FALANTE_01", 12.0, 14.0, "preciso de mais prazo no projeto"),
    ]
    eventos = [
        {
            "nome": "Ana",
            "ts_sec": 10.5,
            "tipo": "legenda",
            "texto": "vamos fechar o orcamento hoje",
        },
        {
            "nome": "Bruno",
            "ts_sec": 12.5,
            "tipo": "legenda",
            "texto": "preciso de mais prazo no projeto",
        },
        # na janela do 1º segmento, Bruno aparece mais como "ativo"
        {"nome": "Bruno", "ts_sec": 10.2, "tipo": "ativo"},
        {"nome": "Bruno", "ts_sec": 10.8, "tipo": "ativo"},
        {"nome": "Bruno", "ts_sec": 11.2, "tipo": "ativo"},
    ]
    rotulado = aplicar_nomes_meet(resultado, eventos)
    assert rotulado[0][0] == "FALANTE_00"
    assert rotulado[1][0] == "FALANTE_01"


def test_mesclar_prioridade_preserva_voce_sem_confirmacao():
    """FR-13.D6: nem legenda forte toma VOCÊ sem confirmação manual."""
    resultado = [("VOCÊ", 10.0, 12.0, "bom dia equipe reuniao")]
    eventos = [
        {
            "nome": "Ana Silva",
            "ts_sec": 10.5,
            "tipo": "legenda",
            "texto": "bom dia equipe reuniao",
        },
        {"nome": "Carlos", "ts_sec": 10.6, "tipo": "ativo"},
    ]
    vozes = {
        "Carlos": {
            "rotulo_origem": "FALANTE_00",
            "embedding": [1.0, 0.0, 0.0],
        }
    }
    centroides = {"FALANTE_00": np.array([1.0, 0.0, 0.0], dtype=np.float32)}
    mesclado = mesclar_prioridade_rotulos(
        resultado,
        eventos,
        vozes_conhecidas=vozes,
        centroides_por_rotulo=centroides,
    )
    assert mesclado[0][0] == "VOCÊ"


def test_sem_legendas_sem_frequencia():
    """FR-13.D6: sem legendas, atividade sozinha nunca nomeia."""
    resultado = [("FALANTE_00", 10.0, 12.0, "qualquer texto")]
    eventos = [
        {"nome": "Ana", "ts_sec": 10.2, "tipo": "ativo"},
        {"nome": "Ana", "ts_sec": 10.8, "tipo": "ativo"},
        {"nome": "Bob", "ts_sec": 11.0, "tipo": "ativo"},
    ]
    rotulado = aplicar_nomes_meet(resultado, eventos)
    assert rotulado[0][0] == "FALANTE_00"