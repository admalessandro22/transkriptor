# -*- coding: utf-8 -*-
"""Correlação de segmentos diarizados com nomes do Meet (FR-5.2/FR-5.3)."""
from __future__ import annotations

import re
from collections import Counter

import numpy as np

from config import JANELA_CORRELACAO_SEG, LIMIAR_IDENTIFICACAO_VOZ
from identificador_voz import similaridade_cosseno

LIMIAR_SIMILARIDADE_LEGENDA = 0.2
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(texto: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(texto or "")}


def similaridade_tokens(a: str, b: str) -> float:
    """Similaridade de Jaccard entre tokens (minúsculas) — FR-5.2."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    uniao = len(ta | tb)
    if uniao == 0:
        return 0.0
    return inter / uniao


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


def correlacionar_por_legenda(
    start: float,
    end: float,
    texto_segmento: str,
    eventos: list[dict],
    janela_margem: float = JANELA_CORRELACAO_SEG,
    limiar: float = LIMIAR_SIMILARIDADE_LEGENDA,
) -> str | None:
    """Nome cuja legenda tem maior Jaccard com o texto do segmento (FR-5.2).

    Considera apenas eventos `tipo=="legenda"` na janela temporal.
    Exige similaridade mínima `limiar` (default 0.2).
    """
    if not texto_segmento or not eventos:
        return None
    inicio = start - janela_margem
    fim = end + janela_margem
    melhor_nome: str | None = None
    melhor_sim = -1.0
    for ev in eventos:
        if str(ev.get("tipo", "")) != "legenda":
            continue
        ts = ev.get("ts_sec", 0.0)
        if not (inicio <= ts <= fim):
            continue
        texto_leg = ev.get("texto") or ""
        nome = ev.get("nome")
        if not nome or not texto_leg:
            continue
        sim = similaridade_tokens(texto_segmento, str(texto_leg))
        if sim > melhor_sim:
            melhor_sim = sim
            melhor_nome = str(nome)
    if melhor_nome is None or melhor_sim < limiar:
        return None
    return melhor_nome


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
    """Aplica nomes do Meet: legenda (texto) tem prioridade sobre frequência (FR-5.2/5.3)."""
    rotulado: list[tuple] = []
    for rot, start, end, texto in resultado:
        # Prioridade: legenda com texto > falante ativo (frequência)
        nome = correlacionar_por_legenda(
            start, end, texto or "", eventos, janela_margem=janela_margem
        )
        if not nome:
            nome = correlacionar_segmento(start, end, eventos, janela_margem)
        if not nome:
            rotulado.append((rot, start, end, texto))
            continue
        if rot == "VOCÊ" and not sobrescrever_voce:
            rotulado.append((rot, start, end, texto))
        else:
            # Nome Meet vence FALANTE_XX, VOCÊ e nomes de vozes_conhecidas.
            rotulado.append((nome, start, end, texto))
    return rotulado


def mesclar_prioridade_rotulos(
    resultado: list[tuple],
    eventos: list[dict],
    vozes_conhecidas: dict | None = None,
    centroides_por_rotulo: dict[str, np.ndarray] | None = None,
    janela_margem: float = JANELA_CORRELACAO_SEG,
) -> list[tuple]:
    """Prioridade FR-5.3: legenda > falante ativo > voz conhecida > VOCÊ > FALANTE_XX.

    Ordem de aplicação (camadas de cima sobrescrevem as de baixo):
      1. vozes conhecidas (embedding)
      2. nomes Meet (legenda por texto, senão frequência de falante ativo)
    """
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
