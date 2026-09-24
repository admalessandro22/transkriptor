# -*- coding: utf-8 -*-
"""Pós-processamento de diarização e preservação de áudio (extraído de Transcritor)."""

from __future__ import annotations

import datetime
import logging
import math
import os
import shutil
from pathlib import Path

from audio_utils import ler_trecho_wav
import config as _config
from config import (
    ARQUIVO_PERFIL_VOZ,
    ARQUIVO_VOZES_CONHECIDAS,
    LIMIAR_IDENTIFICACAO_VOZ,
    LIMIAR_RMS_MIC,
)

logger = logging.getLogger(__name__)


def _destino_sem_colisao(pasta: str, nome: str) -> str:
    """Escolhe destino livre sem apagar áudio de outra reunião."""
    caminho = Path(pasta) / nome
    def ocupado(alvo: Path) -> bool:
        return alvo.exists() or (alvo.suffix.lower() == ".wav" and (
            alvo.with_suffix(".tks").exists() or Path(str(alvo) + ".enc").exists()
        ))

    if not ocupado(caminho):
        return str(caminho)
    indice = 2
    while True:
        candidato = caminho.with_name(f"{caminho.stem}_{indice:02d}{caminho.suffix}")
        if not ocupado(candidato):
            return str(candidato)
        indice += 1


def formatar_intervalo_diarizacao(start: float, end: float) -> str:
    """Formata um intervalo legivel sem produzir duracao visual igual a zero."""
    inicio = max(0, math.floor(float(start)))
    fim = max(inicio + 1, math.ceil(float(end)))
    inicio_fmt = f"{inicio // 60:02d}:{inicio % 60:02d}"
    fim_fmt = f"{fim // 60:02d}:{fim % 60:02d}"
    return f"{inicio_fmt}-{fim_fmt}"


def preservar_audios(modo_ou_criptografar, *caminhos, pasta_audio: str | None = None,
                    criptografar_legado: bool = False, on_status=None, estados=None) -> list:
    """Move WAVs finalizados para PASTA_AUDIO e criptografa se ativo (FR-2.1/2.2)."""
    destinos = []
    pasta = pasta_audio if pasta_audio is not None else _config.PASTA_AUDIO
    os.makedirs(pasta, exist_ok=True)
    from crypto_storage import criptografar_wav
    from politica_privacidade import ProtectionMode, ProtectionState, proteger_audio_tkas

    protegido = modo_ou_criptografar == ProtectionMode.PROTECTED
    criptografar = bool(modo_ou_criptografar) if isinstance(modo_ou_criptografar, bool) else bool(criptografar_legado)

    for caminho in caminhos:
        if not caminho or not os.path.isfile(caminho):
            continue
        try:
            destino = _destino_sem_colisao(pasta, os.path.basename(caminho))
            if os.path.abspath(caminho) != os.path.abspath(destino):
                shutil.move(caminho, destino)
            if protegido:
                protecao = proteger_audio_tkas(Path(destino), ProtectionMode.PROTECTED)
                destino = str(Path(destino).parent / (
                    "restrito" if protecao.state == ProtectionState.PROTECTION_PENDING else ""
                ) / protecao.relative_path)
                if estados is not None:
                    estados.append(protecao)
                if protecao.state == ProtectionState.PROTECTION_PENDING and on_status:
                    on_status("Proteção do áudio pendente; original preservado em área restrita.")
            elif criptografar:
                destino = criptografar_wav(destino)
            destinos.append(destino)
        except Exception:
            logger.exception("Falha ao preservar áudio %s", caminho)
    return destinos


def preservar_audios_transcritor(transcritor, caminhos, pasta_audio: str) -> list:
    from politica_privacidade import modo_efetivo

    transcritor.estados_protecao_audio = []
    return preservar_audios(
        modo_efetivo(), *caminhos, pasta_audio=pasta_audio,
        criptografar_legado=transcritor.criptografar,
        on_status=transcritor.on_status, estados=transcritor.estados_protecao_audio,
    )


def rodar_diarizacao(transcritor, caminho_saida, caminho_wav, *,
                    trechos_audio=None, trechos_mic=None, materializar=True):
    """Pós-processamento: separa falantes e escreve versão diarizada do .txt."""
    import numpy as np

    transcritor.diarizando = True
    try:
        if not transcritor._segmentos:
            transcritor.on_status("Sem segmentos para diarizar.")
            return []

        transcritor.on_status("Iniciando separação de vozes (pós-processamento)...")
        try:
            from diarizador import diarizar

            if trechos_audio is None:
                trechos_audio = []
                if caminho_wav and os.path.isfile(caminho_wav):
                    for start, end, _t in transcritor._segmentos:
                        trechos_audio.append(ler_trecho_wav(caminho_wav, start, end))
                else:
                    trechos_audio = [np.array([], dtype=np.float32)] * len(
                        transcritor._segmentos
                    )

            perfil = None
            if transcritor.identificar_voz:
                from identificador_voz import carregar_perfil

                perfil = carregar_perfil(ARQUIVO_PERFIL_VOZ)

            caminho_mic = getattr(transcritor, "_caminho_wav_mic_salvo", None)
            vozes_conhecidas = {}
            if transcritor.usar_vozes_conhecidas:
                from identificador_voz import carregar_vozes_conhecidas

                vozes_conhecidas = carregar_vozes_conhecidas(ARQUIVO_VOZES_CONHECIDAS)
            resultado, centroides = diarizar(
                trechos_audio,
                transcritor._segmentos,
                num_falantes=transcritor.num_falantes,
                on_status=transcritor.on_status,
                perfil_usuario=perfil,
                limiar_identificacao=LIMIAR_IDENTIFICACAO_VOZ,
                rotulo_usuario=transcritor.rotulo_usuario,
                identificar_ativo=transcritor.identificar_voz,
                caminho_mic_wav=None if trechos_mic is not None else caminho_mic,
                limiar_rms_mic=LIMIAR_RMS_MIC,
                eventos_meet=transcritor.eventos_meet,
                vozes_conhecidas=vozes_conhecidas,
                retornar_centroides=True,
            )
            if trechos_mic is not None and transcritor.identificar_voz:
                from diarizador import reforcar_rotulo_por_mic

                rms_loopback = [float(np.sqrt(np.mean(t * t))) if t.size else 0.0
                                for t in trechos_audio]
                resultado = reforcar_rotulo_por_mic(
                    resultado, None, limiar_rms=LIMIAR_RMS_MIC,
                    rotulo_usuario=transcritor.rotulo_usuario,
                    rms_loopback_por_segmento=rms_loopback,
                    trechos_mic=trechos_mic,
                )
            transcritor._centroides_por_rotulo_ultima = centroides
        except Exception as e:
            transcritor.on_status(f"Erro na diarização: {e}")
            logger.exception("Erro na diarização")
            return []

        if not materializar:
            return resultado
        base, ext = os.path.splitext(caminho_saida)
        caminho_diar = f"{base}_diarizado{ext}"
        linhas = [
            f"=== Transcricao diarizada em {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n\n"
        ]
        for rotulo, start, end, texto in resultado:
            intervalo = formatar_intervalo_diarizacao(start, end)
            linhas.append(f"[{rotulo} {intervalo}] {texto}\n")
        linhas.append("\n=== Fim ===\n")
        texto_diar = "".join(linhas)
        if transcritor.criptografar:
            from crypto_storage import salvar_transcricao

            salvar_transcricao(caminho_diar, texto_diar)
        else:
            with open(caminho_diar, "w", encoding="utf-8") as f:
                f.write(texto_diar)

        transcritor.on_status(f"Diarização concluída: {os.path.basename(caminho_diar)}")
        return resultado
    finally:
        transcritor.diarizando = False
        # Usa método do Transcritor (respeita PASTA_AUDIO monkeypatch nos testes)
        transcritor._preservar_audios(
            caminho_wav, getattr(transcritor, "_caminho_wav_mic_salvo", None)
        )
