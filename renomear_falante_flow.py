# -*- coding: utf-8 -*-
"""Fluxo de renomear FALANTE_XX e persistir embedding (FR-8.5)."""
from __future__ import annotations

import logging
import re

import numpy as np

from config import ARQUIVO_VOZES_CONHECIDAS
from identificador_voz import renomear_falante

logger = logging.getLogger(__name__)

_PADRAO_FALANTE = re.compile(r"^FALANTE_\d{2}$")


def normalizar_rotulo_falante(rotulo: str) -> str | None:
    rotulo = (rotulo or "").strip().upper()
    if _PADRAO_FALANTE.match(rotulo):
        return rotulo
    return None


def rotulos_falante_disponiveis(centroides_por_rotulo: dict) -> list[str]:
    return sorted(k for k in centroides_por_rotulo if _PADRAO_FALANTE.match(k))


def embedding_para_rotulo(centroides_por_rotulo: dict, rotulo: str) -> np.ndarray | None:
    rotulo = normalizar_rotulo_falante(rotulo)
    if rotulo is None:
        return None
    emb = centroides_por_rotulo.get(rotulo)
    if emb is None:
        return None
    return np.asarray(emb, dtype=np.float32)


def persistir_renomeacao_falante(
    rotulo_origem: str,
    novo_nome: str,
    centroides_por_rotulo: dict,
    arquivo=ARQUIVO_VOZES_CONHECIDAS,
) -> str:
    """Persiste renomeação. Retorna o nome salvo. Levanta ValueError se inválido."""
    rotulo = normalizar_rotulo_falante(rotulo_origem)
    if rotulo is None:
        raise ValueError(f"Rótulo inválido: {rotulo_origem}")
    nome = (novo_nome or "").strip()
    if not nome:
        raise ValueError("Nome não pode ser vazio")
    embedding = embedding_para_rotulo(centroides_por_rotulo, rotulo)
    if embedding is None:
        raise ValueError(f"Sem embedding para {rotulo}")
    renomear_falante(rotulo, nome, embedding, arquivo)
    return nome


def corrigir_nome_reuniao(
    caminho_segmentos: str,
    expected_revision: str,
    cluster_falante: str,
    novo_nome: str,
    autor: str = "local",
) -> str:
    """Correção por reunião (T-13.D7): só o mapeamento muda, sem biometria.

    Nunca cadastra perfil de voz; aprendizado persistente é ação separada
    (`persistir_renomeacao_falante`). Devolve a nova revisão.
    """
    from resultado_reuniao import aplicar_correcao

    return aplicar_correcao(
        caminho_segmentos,
        expected_revision=expected_revision,
        speaker_cluster_id=cluster_falante,
        participant_id=None,
        display_name=novo_nome,
        autor=autor,
    )
