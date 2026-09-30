# -*- coding: utf-8 -*-
"""Transcrição do Meet: as legendas agrupadas por falante (T-15.C4 / FR-15.C4).

Segunda saída, no formato das extensões de transcrição: quem falou, quando e
o texto da legenda do Google. Também é a reserva da transcrição principal:
legenda longa sem nenhum segmento do Whisper vira lacuna marcada no TXT.
Os tempos já vêm no relógio do áudio (`ts_sec`) e recebem o atraso estimado
pelo alinhamento (`δ`, negativo quando a legenda chega depois da fala).
"""
from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from config import MEET_BLOCO_FALAS_MAX, MEET_BLOCO_INTERVALO_MS, MEET_LACUNA_MIN_MS
from linha_tempo_falas import Fala, construir_linha_tempo
from resultado_edicao import _hora_curta

NOME_SEM_LEGENDA = "Participante"


def _nome(fala: Fala, proprio: str | None) -> str:
    nome = fala.nome or NOME_SEM_LEGENDA
    return f"{nome} (você)" if proprio and fala.participant_id == proprio and fala.nome else nome


def _deslocada(fala: Fala, atraso_ms: float) -> tuple[int, int]:
    return max(0, round(fala.inicio_ms + atraso_ms)), max(0, round(fala.fim_ms + atraso_ms))


def blocos_meet(eventos: Iterable[Mapping], *, atraso_ms: float, proprio: str | None = None) -> list[dict]:
    """Falas contíguas do mesmo participante (≤ intervalo, ≤ N falas) viram um bloco."""
    blocos: list[dict] = []
    contagem = 0
    for fala in construir_linha_tempo(eventos):
        if not fala.texto:
            continue
        inicio, fim = _deslocada(fala, atraso_ms)
        ultimo = blocos[-1] if blocos else None
        if (ultimo and ultimo["participant_id"] == fala.participant_id and contagem < MEET_BLOCO_FALAS_MAX
                and inicio - ultimo["fim_ms"] <= MEET_BLOCO_INTERVALO_MS):
            ultimo["texto"] += " " + fala.texto
            ultimo["fim_ms"] = max(ultimo["fim_ms"], fim)
            contagem += 1
            continue
        blocos.append({"inicio_ms": inicio, "fim_ms": fim, "participant_id": fala.participant_id,
                       "nome": _nome(fala, proprio), "texto": fala.texto})
        contagem = 1
    return blocos


def lacunas_meet(
    eventos: Iterable[Mapping], segmentos: Sequence, *, atraso_ms: float, proprio: str | None = None
) -> list[dict]:
    """Legendas de pelo menos MEET_LACUNA_MIN_MS sem nenhum segmento do Whisper sobreposto."""
    intervalos = sorted((int(s.start_ms), int(s.end_ms)) for s in segmentos)
    saida = []
    for fala in construir_linha_tempo(eventos):
        inicio, fim = _deslocada(fala, atraso_ms)
        if not fala.texto or fim - inicio < MEET_LACUNA_MIN_MS:
            continue
        if any(a < fim and inicio < b for a, b in intervalos):
            continue
        saida.append({"inicio_ms": inicio, "fim_ms": fim, "participant_id": fala.participant_id,
                      "nome": _nome(fala, proprio), "texto": fala.texto})
    return saida


def exportar_meet_txt(blocos: Sequence[Mapping]) -> str:
    linhas = [f"[{_hora_curta(int(b['inicio_ms']))}] {b['nome']}: {str(b['texto']).strip()}" for b in blocos]
    return "\n".join(linhas) + ("\n" if linhas else "")
