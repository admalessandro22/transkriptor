# -*- coding: utf-8 -*-
"""STT por fonte e fusão cronológica (T-13.C2)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from audio_reader import AudioSource, inspect_audio, iter_audio
from config import AUDIO_BLOCO_MAX_SEG, ECO_SIMILARIDADE_MIN


@dataclass(frozen=True)
class SegmentoSTT:
    segment_id: str
    start_ms: int
    end_ms: int
    source: AudioSource
    text: str
    overlap: bool


def _normalizar_lexico(texto: str) -> list[str]:
    sem_acentos = "".join(
        c
        for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.findall(r"[a-z0-9]+", sem_acentos)


def _similaridade_jaccard(a: str, b: str) -> float:
    ta, tb = set(_normalizar_lexico(a)), set(_normalizar_lexico(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _sobrepoe_tempo(a_ini: int, a_fim: int, b_ini: int, b_fim: int) -> bool:
    return max(a_ini, b_ini) < min(a_fim, b_fim)


def _eco_confirmado(a: SegmentoSTT, b: SegmentoSTT) -> bool:
    """Eco exige sobreposição temporal E similaridade textual; em dúvida, preserva."""
    if a.source == b.source:
        return False
    if not _sobrepoe_tempo(a.start_ms, a.end_ms, b.start_ms, b.end_ms):
        return False
    return _similaridade_jaccard(a.text, b.text) >= ECO_SIMILARIDADE_MIN


def transcrever_fonte(
    path: Path, source: AudioSource, *, model: object
) -> list[SegmentoSTT]:
    caminho = Path(path)
    info = inspect_audio(caminho, source)
    if info.total_frames <= 0:
        return []
    segmentos: list[SegmentoSTT] = []
    for bloco_idx, bloco in enumerate(iter_audio(caminho, source, AUDIO_BLOCO_MAX_SEG)):
        if bloco.samples.size == 0:
            continue
        base_ms = int(bloco.start_frame * 1000 / info.sample_rate)
        encontrados, _info = model.transcribe(bloco.samples, language="pt")
        for seg_idx, segmento in enumerate(list(encontrados)):
            texto = str(getattr(segmento, "text", "")).strip()
            if not texto:
                continue
            ini_ms = base_ms + int(float(getattr(segmento, "start", 0.0)) * 1000)
            fim_ms = base_ms + int(float(getattr(segmento, "end", 0.0)) * 1000)
            segmentos.append(
                SegmentoSTT(
                    segment_id=f"{source.value}-{bloco_idx}-{seg_idx}",
                    start_ms=max(0, ini_ms),
                    end_ms=max(max(0, ini_ms) + 1, fim_ms),
                    source=source,
                    text=texto,
                    overlap=False,
                )
            )
    return segmentos


def mesclar_segmentos(
    loopback: Sequence[SegmentoSTT], microphone: Sequence[SegmentoSTT]
) -> list[SegmentoSTT]:
    """Fusão cronológica com origem explícita e deduplicação só de eco confirmado.

    Fala simultânea independente é preservada com `overlap=True`.
    """
    ordenados = sorted(
        [*loopback, *microphone], key=lambda s: (s.start_ms, s.end_ms, s.segment_id)
    )
    aceitos: list[SegmentoSTT] = []
    for seg in ordenados:
        if any(_eco_confirmado(seg, existente) for existente in aceitos):
            continue
        sobreposto = any(
            _sobrepoe_tempo(seg.start_ms, seg.end_ms, e.start_ms, e.end_ms)
            for e in aceitos
        )
        aceitos.append(
            SegmentoSTT(
                segment_id=seg.segment_id,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                source=seg.source,
                text=seg.text,
                overlap=sobreposto or seg.overlap,
            )
        )
    return aceitos
