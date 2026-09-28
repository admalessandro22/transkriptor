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


def atribuir_segmentos(fundidos, eventos, *, clock_uncertainty_ms: int) -> dict[str, dict]:
    """Produz sugestões auditáveis por ID sem alterar rótulos de voz."""
    from config import CALIBRACAO_IDENTIDADE_VERSAO
    from identidade_reuniao import resolver_atribuicao, serializar_atribuicao

    return {
        segmento.segment_id: serializar_atribuicao(resolver_atribuicao(
            segmento, eventos, clock_uncertainty_ms=clock_uncertainty_ms,
            calibration_version=CALIBRACAO_IDENTIDADE_VERSAO,
        ))
        for segmento in fundidos
    }


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
    """Aplica nomes do Meet somente com confirmação (FR-13.D6).

    Cada segmento passa pelo resolvedor conservador; só `CONFIRMED` (ex.:
    revisão manual) troca o rótulo. Sugestão/incerteza/conflito preservam o
    rótulo original — nunca frequência, nunca adivinhação. Legenda sem match
    não substitui `VOCÊ`; voz conhecida não é sobrescrita sem confirmação.
    """
    from audio_fontes import AudioSource, SegmentoSTT
    from identidade_reuniao import AssignmentStatus, resolver_atribuicao

    rotulado: list[tuple] = []
    for idx, (rot, start, end, texto) in enumerate(resultado):
        segmento = SegmentoSTT(
            segment_id=f"legado-{idx}",
            start_ms=int(float(start) * 1000),
            end_ms=int(float(end) * 1000),
            source=AudioSource.LOOPBACK,
            text=str(texto or ""),
            overlap=False,
        )
        try:
            atribuicao = resolver_atribuicao(
                segmento,
                eventos,
                clock_uncertainty_ms=0,
                calibration_version=None,
            )
        except Exception:  # noqa: BLE001 — em dúvida, preserva o original
            rotulado.append((rot, start, end, texto))
            continue
        if atribuicao.status == AssignmentStatus.CONFIRMED and atribuicao.display_name:
            if rot == "VOCÊ" and not sobrescrever_voce:
                rotulado.append((rot, start, end, texto))
            else:
                rotulado.append((atribuicao.display_name, start, end, texto))
        else:
            rotulado.append((rot, start, end, texto))
    return rotulado


def mesclar_prioridade_rotulos(
    resultado: list[tuple],
    eventos: list[dict],
    vozes_conhecidas: dict | None = None,
    centroides_por_rotulo: dict[str, np.ndarray] | None = None,
    janela_margem: float = JANELA_CORRELACAO_SEG,
) -> list[tuple]:
    """Prioridade FR-13.D6: confirmação manual > voz conhecida/VOCÊ > FALANTE_XX.

    Camadas:
      1. vozes conhecidas (embedding) e VOCÊ existente são preservados;
      2. nomes Meet só entram com confirmação (revisão manual); sugestão,
         empate, homônimos e sobreposição mantêm o rótulo original.
    Frequência de tile nunca nomeia sozinha.
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
