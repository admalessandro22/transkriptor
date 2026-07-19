# -*- coding: utf-8 -*-
"""Correlação de segmentos diarizados com nomes do Meet (FR-8.3/8.4)."""
from __future__ import annotations

from collections import Counter

import numpy as np

from config import JANELA_CORRELACAO_SEG, LIMIAR_IDENTIFICACAO_VOZ
from identificador_voz import similaridade_cosseno


def correlacionar_segmento(
    start: float,
    end: float,
    eventos: list[dict],
    janela_margem: float = JANELA_CORRELACAO_SEG,
) -> str | None:
    """Retorna o nome mais frequente na janela [start-margem, end+margem]."""
    inicio = start - janela_margem
    fim = end + janela_margem
    nomes: list[str] = []
    for ev in eventos:
        ts = ev.get("ts_sec", 0.0)
        if inicio <= ts <= fim:
            nome = ev.get("nome")
            if nome:
                nomes.append(str(nome))
    if not nomes:
        return None
    return Counter(nomes).most_common(1)[0][0]


def aplicar_vozes_conhecidas(
    resultado: list[tuple],
    centroides_por_rotulo: dict[str, np.ndarray],
    vozes_conhecidas: dict,
    limiar: float = LIMIAR_IDENTIFICACAO_VOZ,
) -> list[tuple]:
    """Substitui FALANTE_XX por nomes persistidos quando o embedding coincide."""
    if not vozes_conhecidas or not centroides_por_rotulo:
        return resultado

    mapa: dict[str, str] = {}
    for rotulo, centroide in centroides_por_rotulo.items():
        melhor_nome = None
        melhor_sim = -1.0
        for nome, info in vozes_conhecidas.items():
            emb = info.get("embedding")
            if emb is None:
                continue
            sim = similaridade_cosseno(centroide, np.asarray(emb, dtype=np.float32))
            if sim > melhor_sim and sim >= limiar:
                melhor_sim = sim
                melhor_nome = nome
        if melhor_nome:
            mapa[rotulo] = melhor_nome

    if not mapa:
        return resultado

    return [
        (mapa.get(rot, rot), start, end, texto)
        for rot, start, end, texto in resultado
    ]


def aplicar_nomes_meet(
    resultado: list[tuple],
    eventos: list[dict],
    janela_margem: float = JANELA_CORRELACAO_SEG,
    sobrescrever_voce: bool = True,
) -> list[tuple]:
    rotulado: list[tuple] = []
    for rot, start, end, texto in resultado:
        nome = correlacionar_segmento(start, end, eventos, janela_margem)
        if not nome:
            rotulado.append((rot, start, end, texto))
            continue
        if rot == "VOCÊ" and not sobrescrever_voce:
            rotulado.append((rot, start, end, texto))
        else:
            # Nome Meet vence FALANTE_XX, VOCÊ e nomes de vozes_conhecidas (ex.: Carlos).
            rotulado.append((nome, start, end, texto))
    return rotulado


def mesclar_prioridade_rotulos(
    resultado: list[tuple],
    eventos: list[dict],
    vozes_conhecidas: dict | None = None,
    centroides_por_rotulo: dict[str, np.ndarray] | None = None,
    janela_margem: float = JANELA_CORRELACAO_SEG,
) -> list[tuple]:
    """Prioridade: nome Meet > voz conhecida > rótulo existente (VOCÊ/FALANTE)."""
    mesclado = resultado
    if vozes_conhecidas and centroides_por_rotulo:
        mesclado = aplicar_vozes_conhecidas(mesclado, centroides_por_rotulo, vozes_conhecidas)
    if eventos:
        mesclado = aplicar_nomes_meet(
            mesclado,
            eventos,
            janela_margem=janela_margem,
            sobrescrever_voce=True,
        )
    return mesclado