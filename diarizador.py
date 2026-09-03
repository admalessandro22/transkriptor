# -*- coding: utf-8 -*-
"""Diarização de falantes (pós-processamento).

Usa speechbrain (ECAPA-TDNN, modelo público sem token) para extrair embeddings
de voz de cada segmento transcrito pelo Whisper, e scikit-learn para agrupar
vozes semelhantes em FALANTE_00, FALANTE_01, etc.

O número de falantes é detectado automaticamente por clusterização aglomerativa
com limiar de distância do cosseno.
"""

import logging
import os

import numpy as np

from audio_utils import ler_trecho_wav
from config import (
    MODELO_VOZ_FONTE,
    DIR_MODELO_VOZ,
    SAMPLE_RATE,
    DURACAO_MIN_SEGMENTO,
    LIMIAR_COSSENO_DIARIZACAO,
    MAX_FALANTES_AUTO_DIARIZACAO,
    LIMIAR_IDENTIFICACAO_VOZ,
    ROTULO_USUARIO,
    LIMIAR_RMS_MIC,
    MARGEM_ANTI_ECO,
)
from identificador_voz import identificar_cluster
from correlacionador import mesclar_prioridade_rotulos

logger = logging.getLogger(__name__)

_ENCODER = None


def _carregar_encoder():
    """Carrega o extrator de embeddings de voz (ECAPA-TDNN). Usa cache global."""
    global _ENCODER
    if _ENCODER is not None:
        return _ENCODER
    import torch
    from speechbrain.inference.speaker import SpeakerRecognition

    _ENCODER = SpeakerRecognition.from_hparams(
        source=MODELO_VOZ_FONTE,
        savedir=DIR_MODELO_VOZ,
        run_opts={"device": "cpu"},
    )
    return _ENCODER


def _extrair_embedding(encoder, trecho_audio):
    """Extrai o embedding de voz de um trecho de áudio (np.float32, 16kHz)."""
    import torch

    if trecho_audio.size < int(SAMPLE_RATE * DURACAO_MIN_SEGMENTO):
        return None
    onda = torch.tensor(trecho_audio).float().unsqueeze(0)
    with torch.no_grad():
        emb = encoder.encode_batch(onda)
    return emb.squeeze().cpu().numpy()


def mensagem_progresso_segmentos(atual, total):
    return f"{atual}/{total} segmentos..."


def _rms(trecho: np.ndarray) -> float:
    if trecho.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(trecho.astype(np.float32) ** 2)))


def segmento_tem_voz_mic(trecho: np.ndarray, limiar_rms: float = LIMIAR_RMS_MIC) -> bool:
    return _rms(trecho) >= limiar_rms


def _centroides_por_label(embeddings, labels):
    centroides = {}
    for emb, label in zip(embeddings, labels):
        if label not in centroides:
            centroides[label] = []
        centroides[label].append(emb)
    return {
        label: np.mean(vetores, axis=0)
        for label, vetores in centroides.items()
    }


def _centroides_por_rotulo_falante(embeddings, labels):
    emb_por_label = _centroides_por_label(embeddings, labels)
    return {f"FALANTE_{label:02d}": vetor for label, vetor in emb_por_label.items()}


def _aplicar_nomes_meet_e_vozes(
    resultado,
    embeddings,
    labels,
    eventos_meet,
    vozes_conhecidas,
):
    if not eventos_meet and not vozes_conhecidas:
        return resultado
    centroides = _centroides_por_rotulo_falante(embeddings, labels) if embeddings else {}
    return mesclar_prioridade_rotulos(
        resultado,
        eventos_meet or [],
        vozes_conhecidas=vozes_conhecidas or {},
        centroides_por_rotulo=centroides,
    )


def _finalizar_rotulos_voce(
    resultado,
    embeddings,
    labels,
    perfil_usuario,
    limiar_identificacao,
    rotulo_usuario,
    identificar_ativo,
    caminho_mic_wav,
    limiar_rms_mic,
    eventos_meet=None,
    vozes_conhecidas=None,
    rms_loopback_por_segmento=None,
):
    if identificar_ativo and perfil_usuario is not None and embeddings:
        emb_por_label = _centroides_por_label(embeddings, labels)
        ordem = sorted(emb_por_label.keys())
        centroides_lista = [emb_por_label[k] for k in ordem]
        resultado = aplicar_identificacao_usuario(
            resultado,
            centroides_lista,
            perfil_usuario,
            limiar=limiar_identificacao,
            rotulo_usuario=rotulo_usuario,
        )
    if caminho_mic_wav and identificar_ativo:
        resultado = reforcar_rotulo_por_mic(
            resultado,
            caminho_mic_wav,
            limiar_rms=limiar_rms_mic,
            rotulo_usuario=rotulo_usuario,
            rms_loopback_por_segmento=rms_loopback_por_segmento,
        )
    return _aplicar_nomes_meet_e_vozes(
        resultado,
        embeddings,
        labels,
        eventos_meet,
        vozes_conhecidas,
    )


def aplicar_identificacao_usuario(
    resultado,
    centroides_lista,
    perfil,
    limiar=LIMIAR_IDENTIFICACAO_VOZ,
    rotulo_usuario=ROTULO_USUARIO,
):
    if perfil is None:
        return resultado
    idx = identificar_cluster(centroides_lista, perfil, limiar=limiar)
    if idx is None:
        return resultado
    rotulo_alvo = f"FALANTE_{idx:02d}"
    return [
        (rotulo_usuario if rot == rotulo_alvo else rot, s, e, t)
        for rot, s, e, t in resultado
    ]


def reforcar_rotulo_por_mic(
    resultado,
    caminho_mic,
    limiar_rms=LIMIAR_RMS_MIC,
    rotulo_usuario=ROTULO_USUARIO,
    sample_rate=SAMPLE_RATE,
    rms_loopback_por_segmento=None,
    margem_anti_eco=MARGEM_ANTI_ECO,
):
    """Força rótulo do usuário quando há energia no mic (FR-5.6).

    Guarda anti-eco: se `rms_loopback_por_segmento` estiver disponível, o segmento
    só vira VOCÊ se `rms_mic >= limiar` e `rms_mic > rms_loopback * margem_anti_eco`.
    """
    if not caminho_mic:
        return resultado
    reforcado = []
    for i, (rot, start, end, texto) in enumerate(resultado):
        trecho = ler_trecho_wav(caminho_mic, start, end, sample_rate)
        rms_mic = _rms(trecho)
        if rms_mic < limiar_rms:
            reforcado.append((rot, start, end, texto))
            continue
        if rms_loopback_por_segmento is not None and i < len(rms_loopback_por_segmento):
            rms_lb = float(rms_loopback_por_segmento[i])
            if rms_mic <= rms_lb * margem_anti_eco:
                # Eco do alto-falante no mic — não rotular como VOCÊ
                reforcado.append((rot, start, end, texto))
                continue
        reforcado.append((rotulo_usuario, start, end, texto))
    return reforcado


def _normalizar_segmentos(segmentos):
    """BUG-09: normaliza segmentos sobrepostos e clampa limites."""
    normalizados = []
    end_anterior = 0.0
    for start, end, texto in segmentos:
        start = max(start, end_anterior)
        end = max(end, start + 0.001)
        if start < end:
            normalizados.append((start, end, texto))
            end_anterior = end
    return normalizados


def diarizar(
    trechos_audio,
    segmentos,
    num_falantes=None,
    on_status=None,
    perfil_usuario=None,
    limiar_identificacao=LIMIAR_IDENTIFICACAO_VOZ,
    rotulo_usuario=ROTULO_USUARIO,
    identificar_ativo=True,
    caminho_mic_wav=None,
    limiar_rms_mic=LIMIAR_RMS_MIC,
    eventos_meet=None,
    vozes_conhecidas=None,
    retornar_centroides=False,
):
    """Separa os segmentos por falante.

    Parâmetros:
        trechos_audio: lista de np.ndarray (float32, 16kHz) — um por segmento
        segmentos: [(start_sec, end_sec, texto), ...]
        num_falantes: int ou None (auto-detectar)
        on_status: callback para mensagens de progresso

    Retorna:
        [(rotulo_falante, start_sec, end_sec, texto), ...]
    """
    def status(msg):
        logger.info(msg)
        if on_status:
            on_status(msg)

    def _empacotar(resultado, embeddings, labels, rms_loopback=None):
        final = _finalizar_rotulos_voce(
            resultado,
            embeddings,
            labels,
            perfil_usuario,
            limiar_identificacao,
            rotulo_usuario,
            identificar_ativo,
            caminho_mic_wav,
            limiar_rms_mic,
            eventos_meet,
            vozes_conhecidas,
            rms_loopback_por_segmento=rms_loopback,
        )
        if not retornar_centroides:
            return final
        centroides = _centroides_por_rotulo_falante(embeddings, labels) if embeddings else {}
        return final, centroides

    if not segmentos:
        return ([], {}) if retornar_centroides else []

    # BUG-09: normaliza segmentos sobrepostos
    segmentos = _normalizar_segmentos(segmentos)
    if not segmentos:
        return ([], {}) if retornar_centroides else []

    # Garante que trechos_audio tem o mesmo tamanho que segmentos
    if len(trechos_audio) != len(segmentos):
        # Se houver divergência, usa trechos vazios para os extras
        while len(trechos_audio) < len(segmentos):
            trechos_audio.append(np.array([], dtype=np.float32))

    # RMS do loopback por segmento (guarda anti-eco FR-5.6)
    rms_loopback = [_rms(t) for t in trechos_audio[: len(segmentos)]]

    status("Carregando modelo de vozes...")
    encoder = _carregar_encoder()
    status("Modelo de vozes pronto. Extraindo embeddings...")

    embeddings = []
    indices_validos = []
    total = len(trechos_audio)
    for i, trecho in enumerate(trechos_audio):
        emb = _extrair_embedding(encoder, trecho)
        if emb is not None:
            embeddings.append(emb)
            indices_validos.append(i)
        processados = i + 1
        if processados % 10 == 0 or processados == total:
            status(mensagem_progresso_segmentos(processados, total))

    if len(embeddings) < 2:
        status("Poucos segmentos para clusterizar. Usando 1 falante.")
        resultado = [("FALANTE_00", s, e, t) for s, e, t in segmentos]
        labels_fallback = [0] * len(embeddings)
        return _empacotar(resultado, embeddings, labels_fallback, rms_loopback)

    X = np.array(embeddings)

    from sklearn.cluster import AgglomerativeClustering

    if num_falantes and num_falantes > 0:
        clustering = AgglomerativeClustering(
            n_clusters=min(num_falantes, len(X)),
            metric="cosine",
            linkage="average",
        )
    else:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=LIMIAR_COSSENO_DIARIZACAO,
            metric="cosine",
            linkage="average",
        )
    labels = clustering.fit_predict(X)
    if not num_falantes and len(set(labels)) > MAX_FALANTES_AUTO_DIARIZACAO:
        detectados = len(set(labels))
        status(
            f"Agrupamento automatico instavel ({detectados} grupos); "
            f"limitando a {MAX_FALANTES_AUTO_DIARIZACAO} falantes."
        )
        clustering = AgglomerativeClustering(
            n_clusters=min(MAX_FALANTES_AUTO_DIARIZACAO, len(X)),
            metric="cosine",
            linkage="average",
        )
        labels = clustering.fit_predict(X)
    n_falantes = len(set(labels))
    status(f"Detectados {n_falantes} falante(s).")

    # mapeia de volta para todos os segmentos
    rotulo_map = {}
    resultado = []
    idx_emb = 0
    for i, (start, end, texto) in enumerate(segmentos):
        if i in indices_validos:
            rotulo = f"FALANTE_{labels[idx_emb]:02d}"
            rotulo_map[i] = rotulo
            idx_emb += 1
        else:
            rotulo = _rotulo_proximo(indices_validos, rotulo_map, i)
        resultado.append((rotulo, start, end, texto))

    return _empacotar(resultado, embeddings, labels, rms_loopback)


def _rotulo_proximo(indices_validos, rotulo_map, indice_alvo):
    """Encontra o rótulo do segmento válido mais próximo do indice_alvo."""
    if not indices_validos:
        return "FALANTE_00"
    melhor = min(indices_validos, key=lambda iv: abs(iv - indice_alvo))
    return rotulo_map.get(melhor, "FALANTE_00")
