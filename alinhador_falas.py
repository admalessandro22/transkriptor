# -*- coding: utf-8 -*-
"""Alinhamento legenda do Meet ↔ palavras do Whisper (T-15.C2 / FR-15.C2).

A legenda diz *quem* (o servidor do Google sabe de qual dispositivo veio a
fala); o Whisper diz *o quê* e *quando*, palavra a palavra. A legenda chega
depois da fala (latência do ASR), então primeiro se estima esse atraso `δ`
(`tempo alinhado = tempo da legenda + δ`) pela concordância de palavras, em
grade global e depois por janela, para acompanhar a deriva. Cada palavra vai
para a fala que a cobre; segmentos com duas vozes são cortados na troca.

Nada aqui lê ou devolve conteúdo em diagnóstico: só contagens e tempos.
"""
from __future__ import annotations

import bisect
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from typing import Mapping, Sequence

from audio_fontes import PalavraSTT, SegmentoSTT
from config import (
    ALINHAMENTO_ATRASO_PADRAO_MS,
    ALINHAMENTO_CONCORDANCIA_MIN,
    ALINHAMENTO_FAIXA_MS,
    ALINHAMENTO_FATOR_SO_TEMPO,
    ALINHAMENTO_JANELA_MS,
    ALINHAMENTO_MIN_PARES,
    ALINHAMENTO_PASSO_MS,
    ALINHAMENTO_REFINO_MS,
    ALINHAMENTO_TOLERANCIA_TEXTO_MS,
    ATRIBUICAO_GAP_MAX_MS,
    ATRIBUICAO_TOLERANCIA_MS,
    CALIBRACAO_IDENTIDADE_VERSAO,
    FRAGMENTO_MIN_MS,
    INCERTEZA_TEMPO_MAX_MS,
)
from identidade_reuniao import AssignmentStatus, Atribuicao, serializar_atribuicao
from linha_tempo_falas import Fala, construir_linha_tempo

FONTE = "meet_alinhamento"


def _token(texto: str) -> str:
    sem_acentos = "".join(
        c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn"
    )
    return "".join(re.findall(r"[a-z0-9]+", sem_acentos))


@dataclass(frozen=True)
class Alinhamento:
    atraso_global_ms: float
    atrasos_janela: dict[int, float]
    concordancia: float
    estimado: bool

    def atraso_em(self, t_ms: float) -> float:
        return self.atrasos_janela.get(int(t_ms // ALINHAMENTO_JANELA_MS), self.atraso_global_ms)


@dataclass(frozen=True)
class AtribuicaoPalavra:
    participant_id: str | None
    fala_idx: int | None
    ambigua: bool = False
    forte: bool = False  # contida numa só fala, ou âncora de texto única


@dataclass(frozen=True)
class ResultadoAlinhamento:
    fundidos: list[SegmentoSTT]
    atribuicoes: dict[str, Atribuicao]
    alinhamento: dict | None


# ---------------------------------------------------------------- atraso ----

def _palavras_legenda(falas: Sequence[Fala]) -> list[tuple[str, float]]:
    """Palavras da legenda espalhadas por igual no intervalo da fala."""
    saida = []
    for fala in falas:
        tokens = [t for t in (_token(x) for x in fala.texto.split()) if t]
        passo = (fala.fim_ms - fala.inicio_ms) / len(tokens) if tokens else 0
        saida.extend((tok, fala.inicio_ms + (i + 0.5) * passo) for i, tok in enumerate(tokens))
    return saida


def _pontuar(itens, indice, delta: float, tol: float) -> tuple[float, int]:
    """(peso, pares): cada par vale 1 − |distância|/tol — pico no atraso real."""
    peso, pares = 0.0, 0
    for tok, meio in itens:
        tempos = indice.get(tok)
        if not tempos:
            continue
        alvo = meio - delta
        i = bisect.bisect_left(tempos, alvo)
        distancia = min(abs(tempos[j] - alvo) for j in (i - 1, i) if 0 <= j < len(tempos))
        if distancia <= tol:
            peso += 1.0 - distancia / tol
            pares += 1
    return peso, pares


def _melhor(itens, indice, candidatos, referencia: float) -> tuple[int, int]:
    """Maior peso de concordância; empate fica com o δ mais próximo da referência."""
    melhor = (-1.0, 0.0, 0, 0)
    for delta in candidatos:
        peso, pares = _pontuar(itens, indice, delta, ALINHAMENTO_TOLERANCIA_TEXTO_MS)
        chave = (round(peso, 6), -abs(delta - referencia), delta, pares)
        if chave > melhor:
            melhor = chave
    return melhor[2], melhor[3]


def estimar_atraso(palavras: Sequence[PalavraSTT], falas: Sequence[Fala]) -> Alinhamento:
    itens = [(t, (p.ini_ms + p.fim_ms) / 2) for p in palavras if (t := _token(p.w))]
    legenda = _palavras_legenda(falas)
    padrao = float(ALINHAMENTO_ATRASO_PADRAO_MS)
    if not itens or not legenda:
        return Alinhamento(padrao, {}, 0.0, False)
    indice: dict[str, list[float]] = {}
    for tok, t in legenda:
        indice.setdefault(tok, []).append(t)
    for tempos in indice.values():
        tempos.sort()
    ini, fim = ALINHAMENTO_FAIXA_MS
    delta, pontos = _melhor(itens, indice, range(ini, fim + 1, ALINHAMENTO_PASSO_MS), padrao)
    concordancia = round(pontos / min(len(itens), len(legenda)), 3)
    if pontos < ALINHAMENTO_MIN_PARES:
        return Alinhamento(padrao, {}, concordancia, False)
    por_janela: dict[int, list] = {}
    for item in itens:
        por_janela.setdefault(int(item[1] // ALINHAMENTO_JANELA_MS), []).append(item)
    janelas = {}
    faixa = range(delta - ALINHAMENTO_REFINO_MS, delta + ALINHAMENTO_REFINO_MS + 1, ALINHAMENTO_PASSO_MS)
    for k, grupo in sorted(por_janela.items()):
        d, p = _melhor(grupo, indice, faixa, delta)
        janelas[k] = float(d if p >= max(3, ALINHAMENTO_MIN_PARES // 2) else delta)
    return Alinhamento(float(delta), janelas, concordancia, True)


# ------------------------------------------------------ palavra a palavra ----

def atribuir_palavras(
    palavras: Sequence[PalavraSTT], falas: Sequence[Fala], alinhamento: Alinhamento,
    *, usar_texto: bool = True,
) -> list[AtribuicaoPalavra]:
    tol, gap = ATRIBUICAO_TOLERANCIA_MS, ATRIBUICAO_GAP_MAX_MS
    tokens = [{t for t in (_token(x) for x in f.texto.split()) if t} if usar_texto else set() for f in falas]
    inicios = [f.inicio_ms for f in falas]
    maior = max((f.fim_ms - f.inicio_ms for f in falas), default=0)
    saida = []
    for p in palavras:
        meio = (p.ini_ms + p.fim_ms) / 2
        rel = meio - alinhamento.atraso_em(meio)  # instante no relógio da legenda
        lo = bisect.bisect_left(inicios, rel - gap - maior)
        hi = bisect.bisect_right(inicios, rel + gap)
        perto = [(i, falas[i]) for i in range(lo, hi)]
        dentro = [i for i, f in perto if f.inicio_ms <= rel <= f.fim_ms]
        cobre = [i for i, f in perto if f.inicio_ms - tol <= rel <= f.fim_ms + tol]
        tok = _token(p.w)
        saida.append(_escolher(dentro, cobre, perto, tok, tokens, falas, rel))
    return saida


def _escolher(dentro, cobre, perto, tok, tokens, falas, rel) -> AtribuicaoPalavra:
    if len(dentro) == 1 and (len(cobre) == 1 or tok not in set().union(*(tokens[i] for i in cobre if i != dentro[0]))):
        return AtribuicaoPalavra(falas[dentro[0]].participant_id, dentro[0], forte=True)
    candidatos = cobre or [i for i, _ in perto]
    if not candidatos:
        return AtribuicaoPalavra(None, None)
    com_texto = [i for i in candidatos if tok and tok in tokens[i]]
    if len(com_texto) == 1:
        return AtribuicaoPalavra(falas[com_texto[0]].participant_id, com_texto[0], forte=True)
    pids = {falas[i].participant_id for i in (com_texto or candidatos)}
    if len(pids) == 1 and cobre:
        i = (com_texto or candidatos)[0]
        return AtribuicaoPalavra(falas[i].participant_id, i)
    if cobre:
        return AtribuicaoPalavra(None, None, ambigua=True)
    i = min(candidatos, key=lambda j: min(abs(rel - falas[j].inicio_ms), abs(rel - falas[j].fim_ms)))
    return AtribuicaoPalavra(falas[i].participant_id, i)


# --------------------------------------------------------------- corte ------

def _grupos(pares) -> list[dict]:
    grupos: list[dict] = []
    for par in pares:
        pid = par[1].participant_id
        if grupos and (pid is None or grupos[-1]["pid"] in (None, pid)):
            grupos[-1]["pid"] = grupos[-1]["pid"] or pid
            grupos[-1]["pares"].append(par)
        else:
            grupos.append({"pid": pid, "pares": [par]})
    return grupos


def _curto(grupo: dict) -> bool:
    pares = grupo["pares"]
    duracao = pares[-1][0].fim_ms - pares[0][0].ini_ms
    fraco = not all(a.forte for _, a in pares)
    return fraco and (len(pares) < 2 or duracao < FRAGMENTO_MIN_MS)


def _cortar(seg: SegmentoSTT, das: Sequence[AtribuicaoPalavra]) -> list[tuple[SegmentoSTT, list]]:
    grupos = _grupos(list(zip(seg.words, das)))
    while len(grupos) > 1 and (i := next((k for k, g in enumerate(grupos) if _curto(g)), None)) is not None:
        vizinho = i - 1 if i > 0 else i + 1
        if vizinho < i:
            grupos[vizinho]["pares"].extend(grupos[i]["pares"])
        else:
            grupos[vizinho]["pares"][:0] = grupos[i]["pares"]
        del grupos[i]
        grupos = _grupos([par for g in grupos for par in g["pares"]])
    ambigua = any(a.ambigua for _, a in zip(seg.words, das))
    if len(grupos) == 1:
        return [(replace(seg, overlap=seg.overlap or ambigua), grupos[0]["pares"])]
    saida = []
    for k, g in enumerate(grupos):
        palavras = tuple(p for p, _ in g["pares"])
        inicio = seg.start_ms if k == 0 else palavras[0].ini_ms
        fim = seg.end_ms if k == len(grupos) - 1 else palavras[-1].fim_ms
        saida.append((SegmentoSTT(
            f"{seg.segment_id}-c{k}", inicio, max(inicio + 1, fim), seg.source,
            " ".join(p.w for p in palavras),
            seg.overlap or any(a.ambigua for _, a in g["pares"]), palavras,
        ), g["pares"]))
    return saida


def _atribuicao(pares, falas: Sequence[Fala], fator: float) -> Atribuicao:
    total = sum(max(1, p.fim_ms - p.ini_ms) for p, _ in pares)
    por_pid: Counter = Counter()
    ambigua = 0
    for p, a in pares:
        dur = max(1, p.fim_ms - p.ini_ms)
        if a.ambigua:
            ambigua += dur
        elif a.participant_id:
            por_pid[a.participant_id] += dur
    if ambigua / total > 0.5:
        return Atribuicao(None, None, FONTE, round(ambigua / total, 3), (), AssignmentStatus.CONFLICT,
                          CALIBRACAO_IDENTIDADE_VERSAO)
    if not por_pid:
        return Atribuicao(None, None, FONTE, None, (), AssignmentStatus.UNKNOWN, CALIBRACAO_IDENTIDADE_VERSAO)
    pid, dur = por_pid.most_common(1)[0]
    usadas = sorted({a.fala_idx for _, a in pares if a.participant_id == pid and a.fala_idx is not None})
    nome = next((falas[i].nome for i in usadas if falas[i].nome), None)
    evidencias = tuple(sorted({e for i in usadas for e in falas[i].evento_ids}))[:20]
    status = AssignmentStatus.SUGGESTED if nome else AssignmentStatus.UNKNOWN
    return Atribuicao(pid, nome, FONTE, round(dur / total * fator, 3), evidencias, status,
                      CALIBRACAO_IDENTIDADE_VERSAO)


def combinar_atribuicoes(
    por_texto: Mapping[str, dict], por_alinhamento: Mapping[str, Atribuicao]
) -> dict[str, dict]:
    """Alinhamento substitui a comparação de texto; confirmação manual prevalece."""
    saida = dict(por_texto)
    for segment_id, atribuicao in por_alinhamento.items():
        atual = saida.get(segment_id) or {}
        if atual.get("status") == AssignmentStatus.CONFIRMED.value:
            continue
        if atribuicao.status == AssignmentStatus.UNKNOWN and atual.get("display_name"):
            continue
        saida[segment_id] = serializar_atribuicao(atribuicao)
    return saida


def _idioma_divergente(falas: Sequence[Fala], idioma_transcricao: str | None) -> tuple[str | None, bool]:
    """FR-15.B1: legenda noutro idioma não pode ancorar palavra nenhuma."""
    contagem = Counter(f.idioma for f in falas if f.idioma)
    legenda = contagem.most_common(1)[0][0] if contagem else None
    if not legenda or not idioma_transcricao or idioma_transcricao == "auto":
        return legenda, False
    return legenda, legenda.split("-")[0].lower() != idioma_transcricao.split("-")[0].lower()


def alinhar_segmentos(
    fundidos: Sequence[SegmentoSTT], eventos: Sequence[Mapping], *, incerteza_ms: float,
    idioma_transcricao: str | None = None,
) -> ResultadoAlinhamento:
    """Corta os segmentos na troca de falante e sugere o nome de cada um."""
    fundidos = list(fundidos)
    if incerteza_ms > INCERTEZA_TEMPO_MAX_MS:
        return ResultadoAlinhamento(fundidos, {}, None)
    falas = construir_linha_tempo(eventos)
    palavras = [p for s in fundidos for p in s.words]
    if not falas or not palavras:
        return ResultadoAlinhamento(fundidos, {}, None)
    idioma_legenda, divergente = _idioma_divergente(falas, idioma_transcricao)
    if divergente:
        alinhamento = Alinhamento(float(ALINHAMENTO_ATRASO_PADRAO_MS), {}, 0.0, False)
    else:
        alinhamento = estimar_atraso(palavras, falas)
    por_palavra = atribuir_palavras(palavras, falas, alinhamento, usar_texto=not divergente)
    confiavel = alinhamento.estimado and alinhamento.concordancia >= ALINHAMENTO_CONCORDANCIA_MIN
    fator = 1.0 if confiavel else ALINHAMENTO_FATOR_SO_TEMPO
    novos, atribuicoes, k = [], {}, 0
    for seg in fundidos:
        das = por_palavra[k:k + len(seg.words)]
        k += len(seg.words)
        if not das:
            novos.append(seg)
            continue
        for sub, pares in _cortar(seg, das):
            novos.append(sub)
            atribuicoes[sub.segment_id] = _atribuicao(pares, falas, fator)
    diagnostico = {
        "atraso_global_ms": alinhamento.atraso_global_ms,
        "janelas": len(alinhamento.atrasos_janela),
        "concordancia": alinhamento.concordancia,
        "estimado": alinhamento.estimado,
        "falas": len(falas),
        "palavras": len(palavras),
        "palavras_atribuidas": sum(1 for a in por_palavra if a.participant_id),
        "palavras_ambiguas": sum(1 for a in por_palavra if a.ambigua),
        "segmentos_cortados": len(novos) - len(fundidos),
        "idioma_legenda": idioma_legenda,
        "idioma_divergente": divergente,
    }
    return ResultadoAlinhamento(novos, atribuicoes, diagnostico)
