# -*- coding: utf-8 -*-
"""Linha do tempo de falas do Meet no tempo do áudio (T-15.C2 / FR-15.C2).

Cada `caption_id` ("rtc-<utterance>/<dispositivo>") chega em várias revisões;
aqui elas viram uma fala só: início da primeira chegada, fim da última,
texto e nome da revisão mais nova. Só entram eventos já convertidos pelo
worker (`ts_sec`, e `ts_fim_sec` quando houver) — sem relógio, nada.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Fala:
    fala_id: str
    participant_id: str
    nome: str | None
    inicio_ms: int
    fim_ms: int
    texto: str
    evento_ids: tuple[str, ...]
    idioma: str | None = None  # T-15.B1: idioma da revisão mais nova


def _numero(valor: object) -> float | None:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    return None


def _texto(ev: Mapping) -> str:
    for chave in ("text", "texto"):
        valor = ev.get(chave)
        if isinstance(valor, str):
            return valor.strip()
    return ""


def _nome(ev: Mapping) -> str:
    for chave in ("display_name", "nome"):
        valor = ev.get(chave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return ""


def construir_linha_tempo(eventos: Iterable[Mapping]) -> list[Fala]:
    """Falas ordenadas pelo início; revisões consolidadas por `caption_id`."""
    grupos: dict[str, dict] = {}
    for ev in eventos:
        if not isinstance(ev, Mapping) or str(ev.get("kind", ev.get("tipo", ""))) not in ("caption", "legenda"):
            continue
        inicio = _numero(ev.get("ts_sec"))
        pid, fala_id = ev.get("participant_id"), ev.get("caption_id")
        if inicio is None or not isinstance(pid, str) or not pid or not isinstance(fala_id, str) or not fala_id:
            continue
        fim = _numero(ev.get("ts_fim_sec"))
        revisao = ev.get("caption_revision") if isinstance(ev.get("caption_revision"), int) else -1
        g = grupos.setdefault(fala_id, {"pid": pid, "inicio": inicio, "fim": inicio, "revisao": -2,
                                        "texto": "", "nome": "", "eventos": [], "idioma": None})
        g["inicio"] = min(g["inicio"], inicio)
        g["fim"] = max(g["fim"], fim if fim is not None else inicio)
        if isinstance(ev.get("event_id"), str):
            g["eventos"].append(ev["event_id"])
        if revisao >= g["revisao"]:
            g["revisao"], g["texto"] = revisao, _texto(ev)
            g["nome"] = _nome(ev) or g["nome"]
            g["idioma"] = ev.get("caption_lang") if isinstance(ev.get("caption_lang"), str) else g["idioma"]
        elif not g["nome"]:
            g["nome"] = _nome(ev)
    falas = [
        Fala(fala_id, g["pid"], g["nome"] or None, round(g["inicio"] * 1000), round(g["fim"] * 1000),
             g["texto"], tuple(g["eventos"]), g["idioma"])
        for fala_id, g in grupos.items()
    ]
    return sorted(falas, key=lambda f: (f.inicio_ms, f.fim_ms, f.fala_id))
