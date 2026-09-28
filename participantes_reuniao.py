# -*- coding: utf-8 -*-
"""Participantes de uma reunião a partir do resultado (lista da Central).

Lido na hora, a partir do resultado já carregado (aberto ou decifrado); o
índice continua sem nomes (SEC-13.E4). Nunca devolve texto de fala.
"""
from __future__ import annotations


def participantes_do_resultado(dados: dict) -> dict:
    """Nomes únicos na ordem em que falaram; nunca devolve fala.

    Tolera resultado malformado (ignora o que não tem a forma esperada).
    """
    mapeamento = dados.get("mapeamento") if isinstance(dados, dict) else None
    mapeamento = mapeamento if isinstance(mapeamento, dict) else {}
    segmentos = dados.get("segmentos") if isinstance(dados, dict) else None
    nomes: list[str] = []
    sem_nome: set[str] = set()
    for seg in segmentos if isinstance(segmentos, list) else []:
        if not isinstance(seg, dict):
            continue
        cluster = str(seg.get("speaker_cluster_id", ""))
        manual = mapeamento.get(cluster)
        nome = manual.get("display_name") if isinstance(manual, dict) else None
        if not nome:
            atrib = seg.get("assignment") if isinstance(seg.get("assignment"), dict) else {}
            if atrib.get("status") in ("confirmed", "suggested"):
                nome = atrib.get("display_name")
        nome = str(nome).strip() if nome else ""
        if nome:
            if nome not in nomes:
                nomes.append(nome)
        elif cluster:
            sem_nome.add(cluster)
    return {"participantes": nomes, "sem_nome": len(sem_nome)}
