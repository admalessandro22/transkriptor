# -*- coding: utf-8 -*-
"""Resolução conservadora de identidade por reunião (T-13.D6)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Sequence

from config import (
    CALIBRACAO_IDENTIDADE_VERSAO,
    IDENTIDADE_EPSILON_EMPATE,
    IDENTIDADE_LIMIAR_LEGENDA,
    INCERTEZA_TEMPO_MAX_MS,
    JANELA_CORRELACAO_SEG,
    MODO_AUTO_NOMES,
)


class AssignmentStatus(StrEnum):
    CONFIRMED = "confirmed"
    SUGGESTED = "suggested"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class Atribuicao:
    participant_id: str | None
    display_name: str | None
    source: str
    score: float | None
    evidence_ids: tuple[str, ...]
    status: AssignmentStatus


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(texto: str) -> set[str]:
    sem_acentos = "".join(
        c
        for c in unicodedata.normalize("NFD", str(texto or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return set(_TOKEN_RE.findall(sem_acentos))


def similaridade_lexical(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _texto(ev: Mapping) -> str:
    for chave in ("texto", "text"):
        valor = ev.get(chave)
        if isinstance(valor, str) and valor.strip():
            return valor
    return ""


def _nome(ev: Mapping) -> str:
    for chave in ("display_name", "nome"):
        valor = ev.get(chave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return ""


def _tipo(ev: Mapping) -> str:
    tipo = str(ev.get("kind", ev.get("tipo", ""))).strip().lower()
    return {
        "legenda": "caption",
        "caption": "caption",
        "ativo": "activity",
        "speaker_activity": "activity",
        "manual": "manual",
        "manual_confirm": "manual",
        "google_entry": "entry",
        "heartbeat": "heartbeat",
    }.get(tipo, tipo or "unknown")


def _tempo_ms(ev: Mapping) -> tuple[float | None, bool]:
    """Retorna (ms, absoluto): ts_sec é relativo ao áudio; wall, absoluto."""
    ts = ev.get("ts_sec")
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        return float(ts) * 1000.0, False
    wall = ev.get("client_wall_ms")
    if isinstance(wall, (int, float)) and not isinstance(wall, bool):
        return float(wall), True
    return None, True


def _id_evento(ev: Mapping) -> str:
    for chave in ("event_id", "caption_id", "participant_id"):
        valor = ev.get(chave)
        if isinstance(valor, str) and valor:
            return valor
    return ""


def _desconhecida(source: str) -> Atribuicao:
    return Atribuicao(None, None, source, None, (), AssignmentStatus.UNKNOWN)


def resolver_atribuicao(
    segmento,
    eventos: Sequence[Mapping],
    *,
    clock_uncertainty_ms: int,
    calibration_version: str | None,
) -> Atribuicao:
    """Resolve com precisão antes de cobertura; sem prova, abstém-se.

    Precedência: manual → entry oficial → legenda compatível+tempo → voz/atividade
    (auxiliar). Empate, homônimos sem id, sobreposição e relógio incerto geram
    pendência, nunca o nome mais frequente. Fora do modo automático calibrado,
    o teto é SUGGESTED (só manual confirma).
    """
    del calibration_version  # versão registrada na evidência; comportamento fixo
    inicio_ms = int(getattr(segmento, "start_ms", 0))
    fim_ms = int(getattr(segmento, "end_ms", inicio_ms))
    texto = str(getattr(segmento, "text", "") or "")
    sobreposto = bool(getattr(segmento, "overlap", False))
    seg_id = str(getattr(segmento, "segment_id", "") or "")
    relogio_ok = int(clock_uncertainty_ms) <= INCERTEZA_TEMPO_MAX_MS
    eventos = [e for e in (eventos or []) if isinstance(e, Mapping)]

    def na_janela(ev_ms: float | None) -> bool:
        if ev_ms is None:
            return False
        margem = JANELA_CORRELACAO_SEG * 1000.0
        return (inicio_ms - margem) <= ev_ms <= (fim_ms + margem)

    # 1. Confirmação manual prevalece (por segmento ou por janela certa).
    for ev in eventos:
        if _tipo(ev) != "manual":
            continue
        nome = _nome(ev)
        if not nome:
            continue
        if (ev.get("segment_id") and str(ev.get("segment_id")) == seg_id) or na_janela(
            _tempo_ms(ev)[0]
        ):
            return Atribuicao(
                ev.get("participant_id"),
                nome,
                "manual",
                1.0,
                (_id_evento(ev),) if _id_evento(ev) else (),
                AssignmentStatus.CONFIRMED,
            )

    if sobreposto:
        return _desconhecida("overlap")

    # 2-3. Entry oficial e legendas: candidatos com tempo e léxico.
    candidatos: list[tuple[float, str | None, str, str, str]] = []
    for ev in eventos:
        tipo = _tipo(ev)
        if tipo not in ("entry", "caption"):
            continue
        nome = _nome(ev)
        if not nome:
            continue
        ev_ms, absoluto = _tempo_ms(ev)
        if tipo == "entry":
            pid = ev.get("participant_id")
            if not pid or absoluto or not relogio_ok or not na_janela(ev_ms):
                continue
            candidatos.append((1.0, str(pid), nome, "google_entry", _id_evento(ev)))
            continue
        if tipo == "caption":
            if ev_ms is not None and not absoluto and relogio_ok and not na_janela(ev_ms):
                continue
            escore = similaridade_lexical(texto, _texto(ev))
            if escore < IDENTIDADE_LIMIAR_LEGENDA:
                continue
            candidatos.append(
                (escore, ev.get("participant_id"), nome, "caption", _id_evento(ev))
            )
    if not candidatos:
        return _desconhecida("caption" if any(_tipo(e) == "caption" for e in eventos) else "unknown")
    candidatos.sort(key=lambda c: c[0], reverse=True)
    melhor, segundo = candidatos[0], candidatos[1] if len(candidatos) > 1 else None
    if segundo is not None and (melhor[0] - segundo[0]) <= IDENTIDADE_EPSILON_EMPATE:
        return Atribuicao(None, None, melhor[3], round(melhor[0], 3), (), AssignmentStatus.CONFLICT)
    nomes = {c[2] for c in candidatos if abs(c[0] - melhor[0]) <= IDENTIDADE_EPSILON_EMPATE}
    if len(nomes) > 1:
        return Atribuicao(None, None, melhor[3], round(melhor[0], 3), (), AssignmentStatus.CONFLICT)
    mesmo_nome = [c for c in candidatos if c[2] == melhor[2]]
    ids = {c[1] for c in mesmo_nome if c[1]}
    if len(ids) > 1:
        return Atribuicao(None, None, melhor[3], round(melhor[0], 3), (), AssignmentStatus.CONFLICT)
    pid = melhor[1]
    evidencias = tuple(c[4] for c in mesmo_nome if c[4])
    if MODO_AUTO_NOMES:
        return Atribuicao(pid, melhor[2], melhor[3], round(melhor[0], 3), evidencias, AssignmentStatus.CONFIRMED)
    return Atribuicao(pid, melhor[2], melhor[3], round(melhor[0], 3), evidencias, AssignmentStatus.SUGGESTED)


def avaliar_atribuicoes(pares: Sequence[tuple[Atribuicao, str | None]]) -> dict:
    """Precisão seletiva, cobertura elegível/total, abstinências (D6/G3)."""
    nomeados = [p for p, _ in pares if p.status in (AssignmentStatus.CONFIRMED, AssignmentStatus.SUGGESTED) and p.display_name]
    elegiveis = [(p, v) for p, v in pares if v]
    corretos = sum(1 for p, v in elegiveis if p.display_name == v)
    total = len(pares)
    abstencoes = sum(1 for p, _ in pares if p.status in (AssignmentStatus.UNKNOWN, AssignmentStatus.CONFLICT))
    return {
        "total": total,
        "nomeados": len(nomeados),
        "corretos": corretos,
        "precisao_seletiva": (corretos / len(nomeados)) if nomeados else 0.0,
        "cobertura_elegivel": (corretos / len(elegiveis)) if elegiveis else 0.0,
        "cobertura_total": (corretos / total) if total else 0.0,
        "abstencoes": abstencoes,
        "calibracao": CALIBRACAO_IDENTIDADE_VERSAO,
    }
