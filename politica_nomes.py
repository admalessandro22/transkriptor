# -*- coding: utf-8 -*-
"""Nomes do Meet aplicados sozinhos quando a evidência é forte (T-15.C3 / FR-15.C3).

DP-15-02 ("sim, desde já"): o alinhamento com a legenda do Meet é prova de
autoria; acima dos limiares (provisórios até a T-15.F1) a sugestão vira
confirmação automática — marcada `auto`, visível e desfazível pela correção.
A comparação de texto (relógio incerto) nunca é aplicada sozinha, e uma
correção manual do cluster nunca é sobrescrita.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Mapping, Sequence

from config import (
    NOME_AUTO_CONFIANCA_MIN,
    NOME_AUTO_DURACAO_MIN_S,
    NOME_AUTO_PARTICIPACAO_MIN,
    NOMES_AUTO_MEET,
)
from resultado_edicao import SegmentoResultado

FONTES_AUTO = frozenset({"meet_alinhamento", "meet_proprio"})
ORIGEM_AUTO = "meet_auto"


def _confirmavel(seg: SegmentoResultado) -> bool:
    a = seg.assignment
    return bool(
        isinstance(a, Mapping) and a.get("status") == "suggested" and a.get("source") in FONTES_AUTO
        and a.get("display_name") and a.get("participant_id") and not seg.overlap
        and isinstance(a.get("confidence"), (int, float)) and a["confidence"] >= NOME_AUTO_CONFIANCA_MIN
    )


def _nomes_de_cluster(segmentos: Sequence[SegmentoResultado]) -> dict[str, dict]:
    """Participante dominante por duração, se cobrir o cluster e não houver homônimo."""
    total: Counter = Counter()
    por_cluster: dict[str, Counter] = {}
    nomes: dict[str, str] = {}
    for seg in segmentos:
        duracao = max(0, seg.end_ms - seg.start_ms)
        total[seg.speaker_cluster_id] += duracao
        a = seg.assignment
        if isinstance(a, Mapping) and a.get("auto"):
            por_cluster.setdefault(seg.speaker_cluster_id, Counter())[a["participant_id"]] += duracao
            nomes[a["participant_id"]] = a["display_name"]
    saida = {}
    for cluster, contagem in por_cluster.items():
        pid, duracao = contagem.most_common(1)[0]
        homonimos = sum(1 for outro in contagem if nomes[outro] == nomes[pid]) > 1
        participacao = duracao / total[cluster] if total[cluster] else 0.0
        if (not homonimos and participacao >= NOME_AUTO_PARTICIPACAO_MIN
                and duracao / 1000 >= NOME_AUTO_DURACAO_MIN_S):
            saida[cluster] = {"participant_id": pid, "display_name": nomes[pid], "origem": ORIGEM_AUTO,
                              "confianca": round(participacao, 3)}
    return saida


def aplicar_politica(
    segmentos: Sequence[SegmentoResultado], mapeamento: Mapping[str, dict] | None = None
) -> tuple[tuple[SegmentoResultado, ...], dict[str, dict]]:
    """(segmentos com confirmações automáticas, mapeamento com os nomes de cluster)."""
    existente = {k: dict(v) for k, v in (mapeamento or {}).items()}
    if not NOMES_AUTO_MEET:
        return tuple(segmentos), existente
    novos = tuple(
        replace(s, assignment={**s.assignment, "status": "confirmed", "auto": True}) if _confirmavel(s) else s
        for s in segmentos
    )
    for cluster, entrada in _nomes_de_cluster(novos).items():
        atual = existente.get(cluster)
        if not (isinstance(atual, Mapping) and atual.get("display_name") and atual.get("origem") != ORIGEM_AUTO):
            existente[cluster] = entrada
    return novos, existente
