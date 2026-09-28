# -*- coding: utf-8 -*-
"""Alinhamento explícito entre STT, origem de áudio e diarização."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from audio_fontes import SegmentoSTT
from resultado_reuniao import SegmentoResultado


@dataclass(frozen=True)
class ResultadoProcessamento:
    txt_path: Path
    segmentos: tuple[SegmentoResultado, ...]
    warnings: tuple[str, ...] = ()
    gerar_copia_tkpt: bool = False


def criar_segmentos(
    fundidos: Sequence[SegmentoSTT],
    diarizados: Sequence[tuple[str, float, float, str]] = (),
    atribuicoes: Mapping[str, Mapping] | None = None,
) -> tuple[tuple[SegmentoResultado, ...], tuple[str, ...]]:
    """Correlaciona por intervalo e texto; divergência deixa o rótulo pendente."""
    por_chave: dict[tuple[int, int, str], list[str]] = {}
    for rotulo, inicio, fim, texto in diarizados:
        chave = (round(inicio * 1000), round(fim * 1000), str(texto).strip())
        por_chave.setdefault(chave, []).append(str(rotulo))
    alinhamento_falhou = False
    saida = []
    for segmento in fundidos:
        chave = (segmento.start_ms, segmento.end_ms, segmento.text.strip())
        rotulos = por_chave.get(chave, [])
        if diarizados and len(rotulos) != 1:
            alinhamento_falhou = True
        rotulo = rotulos.pop() if len(rotulos) == 1 else "FALANTE_00"
        saida.append(SegmentoResultado(
            segment_id=segmento.segment_id,
            start_ms=segmento.start_ms,
            end_ms=segmento.end_ms,
            audio_source=segmento.source.value,
            text=segmento.text,
            speaker_cluster_id=rotulo,
            overlap=segmento.overlap,
            assignment=(atribuicoes or {}).get(segmento.segment_id),
        ))
    if any(por_chave.values()):
        alinhamento_falhou = True
    return tuple(saida), (("segment_alignment_failed",) if alinhamento_falhou else ())
