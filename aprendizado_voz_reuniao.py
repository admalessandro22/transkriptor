# -*- coding: utf-8 -*-
"""Extrai, sob demanda, uma voz da reunião escolhida para cadastro explícito.

Não guarda centroides de todas as reuniões: biometria persistente só é escrita
pela ação confirmada de ``central_api``.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from config import (
    APRENDIZADO_VOZ_AMOSTRAS_MAX,
    APRENDIZADO_VOZ_FRACAO_COHERENTE,
    APRENDIZADO_VOZ_MIN_AMOSTRAS,
    APRENDIZADO_VOZ_TOTAL_MIN_MS,
    APRENDIZADO_VOZ_TRECHO_MAX_MS,
    APRENDIZADO_VOZ_TRECHO_MIN_MS,
    LIMIAR_COSSENO_DIARIZACAO,
    PASTA_TRANSCRICOES,
)


class AprendizadoIndisponivel(ValueError):
    def __init__(self, mensagem: str, status: int = 422):
        super().__init__(mensagem)
        self.status = status


def _candidatos(segmentos: list[dict], rotulo: str, *, tem_mic: bool):
    por_fonte: dict[str, list[dict]] = {"loopback": [], "microphone": []}
    for seg in segmentos:
        fonte = seg.get("audio_source")
        if (seg.get("speaker_cluster_id") != rotulo or seg.get("overlap")
                or fonte not in por_fonte or (fonte == "microphone" and not tem_mic)):
            continue
        try:
            duracao = int(seg["end_ms"]) - int(seg["start_ms"])
        except (KeyError, TypeError, ValueError):
            continue
        if duracao >= APRENDIZADO_VOZ_TRECHO_MIN_MS:
            por_fonte[fonte].append(seg)
    elegiveis = [
        (fonte, sorted(grupo, key=lambda s: int(s["end_ms"]) - int(s["start_ms"]), reverse=True)[:APRENDIZADO_VOZ_AMOSTRAS_MAX])
        for fonte, grupo in por_fonte.items() if len(grupo) >= APRENDIZADO_VOZ_MIN_AMOSTRAS
    ]
    elegiveis = [
        (fonte, grupo) for fonte, grupo in elegiveis
        if sum(min(int(s["end_ms"]) - int(s["start_ms"]), APRENDIZADO_VOZ_TRECHO_MAX_MS)
               for s in grupo) >= APRENDIZADO_VOZ_TOTAL_MIN_MS
    ]
    if not elegiveis:
        raise AprendizadoIndisponivel(
            "Este falante não tem trechos de voz suficientes sem sobreposição nesta reunião. "
            "Use outra reunião ou cadastre uma amostra de microfone."
        )
    return max(
        elegiveis,
        key=lambda item: sum(min(int(s["end_ms"]) - int(s["start_ms"]),
                                 APRENDIZADO_VOZ_TRECHO_MAX_MS) for s in item[1]),
    )


def _centroide_coerente(trechos: list[np.ndarray]) -> np.ndarray:
    from diarizador import _carregar_encoder, _extrair_embedding
    from identificador_voz import media_embeddings, similaridade_cosseno

    try:
        encoder = _carregar_encoder()
    except Exception as exc:  # noqa: BLE001 — modelo local ausente/corrompido
        raise AprendizadoIndisponivel("Modelo de voz local indisponível.", 503) from exc
    vetores = []
    for trecho in trechos:
        try:
            emb = _extrair_embedding(encoder, trecho)
        except Exception as exc:  # noqa: BLE001 — falha local de inferência
            raise AprendizadoIndisponivel("Modelo de voz local indisponível.", 503) from exc
        if emb is None:
            continue
        vetor = np.asarray(emb, dtype=np.float32)
        if (vetor.shape == (192,) and np.all(np.isfinite(vetor))
                and np.linalg.norm(vetor) > 0):
            vetores.append(vetor)
    if len(vetores) < APRENDIZADO_VOZ_MIN_AMOSTRAS:
        raise AprendizadoIndisponivel("O áudio deste falante não forneceu duas amostras de voz válidas.")
    melhor = max(
        vetores,
        key=lambda v: sum(similaridade_cosseno(v, outro) for outro in vetores),
    )
    coerentes = [
        v for v in vetores
        if similaridade_cosseno(v, melhor) >= 1.0 - LIMIAR_COSSENO_DIARIZACAO
    ]
    if (len(coerentes) < APRENDIZADO_VOZ_MIN_AMOSTRAS
            or len(coerentes) < math.ceil(len(vetores) * APRENDIZADO_VOZ_FRACAO_COHERENTE)):
        raise AprendizadoIndisponivel(
            "As amostras deste falante não são consistentes; a voz não foi cadastrada."
        )
    return media_embeddings(coerentes)


def embedding_da_reuniao(
    meeting_id: str, rotulo: str, expected_revision: str,
    *, raiz: Path | str = PASTA_TRANSCRICOES,
) -> np.ndarray:
    """Confere identidade, revisão e áudios antes de calcular biometria em memória."""
    from audio_reader import AudioSource
    from audio_trechos import extrair_trechos
    from fila_processamento import FilaProcessamento, PADRAO_ID
    from politica_privacidade import ProtectionMode
    from resultado_reuniao import StageState, carregar_manifesto, validar_manifesto_para_job
    from resultado_storage import FORMATO_CIFRADO, ResultadoStorage

    if not PADRAO_ID.fullmatch(str(meeting_id or "")):
        raise AprendizadoIndisponivel("Reunião inválida.", 400)
    if not expected_revision:
        raise AprendizadoIndisponivel("Revisão da reunião ausente. Atualize a página.", 400)
    try:
        raiz = Path(raiz).resolve(strict=True)
    except OSError as exc:
        raise AprendizadoIndisponivel("Dados de reuniões indisponíveis.", 503) from exc
    try:
        job = FilaProcessamento(str(raiz)).obter(meeting_id)
    except (OSError, ValueError, KeyError) as exc:
        raise AprendizadoIndisponivel("Reunião não encontrada.", 404) from exc
    if job.estado != "ready" or not job.manifesto_resultado or not job.resultado:
        raise AprendizadoIndisponivel("Esta reunião ainda não terminou o processamento.", 409)
    fontes = [Path(job.audio)] + ([Path(job.mic)] if job.mic else [])
    try:
        validar_manifesto_para_job(
            resultado=Path(job.resultado), manifesto=Path(job.manifesto_resultado),
            fontes_audio=fontes, raiz=raiz,
        )
        manifesto = carregar_manifesto(Path(job.manifesto_resultado))
        if manifesto.meeting_id != meeting_id:
            raise ValueError("ID do manifesto divergente")
        modo = (ProtectionMode.PROTECTED if manifesto.segments_ref.format == FORMATO_CIFRADO
                else ProtectionMode.COMPATIBLE)
        dados = ResultadoStorage(raiz, modo).load(manifesto.segments_ref)
    except (OSError, ValueError) as exc:
        raise AprendizadoIndisponivel(
            "Áudio ou resultado da reunião indisponível ou inválido.", 422
        ) from exc
    if dados.get("revision") != expected_revision:
        raise AprendizadoIndisponivel("Revisão divergente. Atualize a reunião e tente de novo.", 409)
    if manifesto.stage_status.get("diarizacao") is not StageState.COMPLETE:
        raise AprendizadoIndisponivel("A separação de vozes desta reunião não está completa.")
    segmentos = dados.get("segmentos") or []
    if not any(s.get("speaker_cluster_id") == rotulo for s in segmentos):
        raise AprendizadoIndisponivel("Falante não encontrado nesta reunião.", 404)
    fonte, grupo = _candidatos(segmentos, rotulo, tem_mic=bool(job.mic))
    intervalos = [
        (int(s["start_ms"]) / 1000.0,
         min(int(s["end_ms"]), int(s["start_ms"]) + APRENDIZADO_VOZ_TRECHO_MAX_MS) / 1000.0,
         "")
        for s in grupo
    ]
    caminho = Path(job.mic if fonte == "microphone" else job.audio)
    try:
        trechos = extrair_trechos(caminho, AudioSource(fonte), intervalos)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AprendizadoIndisponivel("Não foi possível ler o áudio desta reunião.") from exc
    centroide = _centroide_coerente(trechos)
    # Uma correção concorrente pode alterar a identidade do rótulo enquanto o
    # modelo trabalha. Nesse caso o usuário precisa confirmar a revisão nova.
    atual = carregar_manifesto(Path(job.manifesto_resultado))
    atual_dados = ResultadoStorage(raiz, modo).load(atual.segments_ref)
    if atual_dados.get("revision") != expected_revision:
        raise AprendizadoIndisponivel("Revisão divergente. Atualize a reunião e tente de novo.", 409)
    return centroide
