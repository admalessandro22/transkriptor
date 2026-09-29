# -*- coding: utf-8 -*-
"""Relógio da extensão Meet no tempo do áudio (T-15.A2 / FR-15.A2).

A ponte pinga o background; a troca de menor ida-e-volta dá o desvio entre o
relógio de parede do navegador e o do app. Cada legenda chega com o horário
da página e uma amostra página↔parede do mesmo instante; a ponte converte o
início e o fim da fala para `time.monotonic_ns()` — a mesma base do primeiro
frame de áudio — e o worker só subtrai.
"""
from __future__ import annotations

import asyncio
import json
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from config import (
    INCERTEZA_TEMPO_MAX_MS,
    RELOGIO_AMOSTRAS_MAX,
    RELOGIO_FOLGA_FUTURO_MS,
    RELOGIO_INTERVALO_INICIAL_S,
    RELOGIO_INTERVALO_S,
    RELOGIO_PINGS_INICIAIS,
    RELOGIO_PINGS_PENDENTES_MAX,
)

RESOLUCAO_RELOGIO_MS = 1.0  # Date.now() tem resolução de 1 ms
CAMPOS_DO_SERVIDOR = (
    "speech_started_monotonic_ns",
    "speech_last_monotonic_ns",
    "clock_uncertainty_ms",
)

__all__ = [
    "AmostraRelogio",
    "CAMPOS_DO_SERVIDOR",
    "RelogiosConexao",
    "carimbar_fala",
    "pingar",
    "INCERTEZA_TEMPO_MAX_MS",
    "RESOLUCAO_RELOGIO_MS",
    "agora_wall_ms",
    "eventos_no_tempo_do_audio",
    "melhor_offset",
    "para_monotonic_servidor_ns",
]


@dataclass(frozen=True)
class AmostraRelogio:
    """Um ping do servidor e a resposta do cliente com o relógio dele."""

    n: int
    envio_mono_ns: int
    envio_wall_ns: int
    recebido_mono_ns: int
    cliente_wall_ms: float


def agora_wall_ms() -> float:
    return time.time_ns() / 1_000_000


def _finito(valor: object) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def melhor_offset(amostras: Iterable[AmostraRelogio]) -> tuple[float, float] | None:
    """(desvio cliente−servidor em ms, incerteza em ms) pela menor ida-e-volta."""
    melhor: tuple[float, AmostraRelogio] | None = None
    for amostra in amostras:
        rtt_ms = (amostra.recebido_mono_ns - amostra.envio_mono_ns) / 1_000_000
        if rtt_ms < 0 or not _finito(amostra.cliente_wall_ms):
            continue
        if melhor is None or rtt_ms < melhor[0]:
            melhor = (rtt_ms, amostra)
    if melhor is None:
        return None
    rtt_ms, amostra = melhor
    offset_ms = amostra.cliente_wall_ms - (amostra.envio_wall_ns / 1_000_000 + rtt_ms / 2)
    return offset_ms, rtt_ms / 2 + RESOLUCAO_RELOGIO_MS


def para_monotonic_servidor_ns(
    t_pagina_ms: float,
    *,
    page_perf_ms: float,
    page_wall_ms: float,
    offset_ms: float,
    agora_mono_ns: int,
    agora_wall_ns: int,
) -> int:
    """Horário da página → parede do cliente → parede do app → monotônico do app."""
    cliente_wall_ms = t_pagina_ms - (page_perf_ms - page_wall_ms)
    servidor_wall_ns = round((cliente_wall_ms - offset_ms) * 1_000_000)
    return agora_mono_ns - (agora_wall_ns - servidor_wall_ns)


class RelogiosConexao:
    """Pings pendentes e amostras por conexão lógica; thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._por_conexao: dict[str, dict] = {}

    def iniciar_ping(self, connection_id: str) -> dict:
        with self._lock:
            reg = self._por_conexao.setdefault(
                connection_id, {"pings": {}, "amostras": deque(maxlen=RELOGIO_AMOSTRAS_MAX), "proximo": 0}
            )
            n = reg["proximo"]
            reg["proximo"] += 1
            if len(reg["pings"]) >= RELOGIO_PINGS_PENDENTES_MAX:
                reg["pings"].pop(next(iter(reg["pings"])))
            reg["pings"][n] = (time.monotonic_ns(), time.time_ns())
        return {"tipo": "relogio_ping", "connection_id": connection_id, "n": n}

    def registrar_pong(self, connection_id: str, n: object, *, cliente_wall_ms: object) -> None:
        recebido = time.monotonic_ns()
        if not isinstance(n, int) or isinstance(n, bool) or not _finito(cliente_wall_ms):
            return
        with self._lock:
            reg = self._por_conexao.get(connection_id)
            envio = reg["pings"].pop(n, None) if reg is not None else None
            if envio is None:
                return
            reg["amostras"].append(
                AmostraRelogio(n, envio[0], envio[1], recebido, float(cliente_wall_ms))
            )

    def relogio_de(self, connection_id: str) -> tuple[float, float] | None:
        with self._lock:
            reg = self._por_conexao.get(connection_id)
            amostras = list(reg["amostras"]) if reg is not None else []
        return melhor_offset(amostras)

    def esquecer(self, connection_id: str) -> None:
        with self._lock:
            self._por_conexao.pop(connection_id, None)


def carimbar_fala(
    evento: dict,
    relogio: tuple[float, float] | None,
    *,
    agora_mono_ns: int,
    agora_wall_ns: int,
) -> dict:
    """Converte o intervalo da fala (schema 2) para o monotônico do app.

    Campos de servidor vindos do cliente são descartados antes; sem relógio,
    sem amostra página↔parede ou com resultado no futuro, nada é carimbado.
    """
    for campo in CAMPOS_DO_SERVIDOR:
        evento.pop(campo, None)
    if relogio is None or evento.get("schema_version") != 2 or evento.get("kind") != "caption":
        return evento
    perf, wall = evento.get("page_perf_ms"), evento.get("page_wall_ms")
    if not (_finito(perf) and _finito(wall)):
        return evento
    offset_ms, incerteza_ms = relogio
    inicio, fim = (
        para_monotonic_servidor_ns(
            evento[campo], page_perf_ms=perf, page_wall_ms=wall, offset_ms=offset_ms,
            agora_mono_ns=agora_mono_ns, agora_wall_ns=agora_wall_ns,
        )
        for campo in ("caption_started_ms", "caption_last_ms")
    )
    if fim > agora_mono_ns + int((incerteza_ms + RELOGIO_FOLGA_FUTURO_MS) * 1_000_000):
        return evento
    evento["speech_started_monotonic_ns"] = inicio
    evento["speech_last_monotonic_ns"] = fim
    evento["clock_uncertainty_ms"] = incerteza_ms + RESOLUCAO_RELOGIO_MS  # amostra da página
    return evento


async def pingar(enviar, relogios: RelogiosConexao, connection_id: str) -> None:
    """Rajada inicial de pings e um a cada RELOGIO_INTERVALO_S enquanto conectado."""
    enviados = 0
    while True:
        await enviar(json.dumps(relogios.iniciar_ping(connection_id)))
        enviados += 1
        espera = RELOGIO_INTERVALO_INICIAL_S if enviados < RELOGIO_PINGS_INICIAIS else RELOGIO_INTERVALO_S
        await asyncio.sleep(espera)


def eventos_no_tempo_do_audio(
    eventos: Sequence[Mapping], primeiro_frame_ns: int | None
) -> tuple[list[dict], float | None]:
    """Acrescenta `ts_sec` (relativo ao 1º frame) e devolve a maior incerteza.

    Sem primeiro frame, ou sem evento carimbado pela ponte, a incerteza é
    `None` e o chamador mantém o relógio como incerto. Fala anterior ao
    início do áudio não ganha tempo negativo.
    """
    saida: list[dict] = []
    incertezas: list[float] = []
    for evento in eventos:
        copia = dict(evento)
        inicio_ns = copia.get("speech_started_monotonic_ns")
        incerteza = copia.get("clock_uncertainty_ms")
        if (
            primeiro_frame_ns is not None
            and isinstance(inicio_ns, int) and not isinstance(inicio_ns, bool)
            and _finito(incerteza)
            and inicio_ns >= primeiro_frame_ns
        ):
            copia["ts_sec"] = (inicio_ns - primeiro_frame_ns) / 1_000_000_000
            incertezas.append(float(incerteza))
        saida.append(copia)
    return saida, (max(incertezas) if incertezas else None)
