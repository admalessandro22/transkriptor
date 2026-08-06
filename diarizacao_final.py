# -*- coding: utf-8 -*-
"""Pós-processamento de diarização e preservação de áudio (extraído de Transcritor)."""

from __future__ import annotations

import datetime
import logging
import os
import shutil

from audio_utils import ler_trecho_wav
import config as _config
from config import (
    ARQUIVO_PERFIL_VOZ,
    ARQUIVO_VOZES_CONHECIDAS,
    LIMIAR_IDENTIFICACAO_VOZ,
    LIMIAR_RMS_MIC,
)

logger = logging.getLogger(__name__)


def preservar_audios(criptografar: bool, *caminhos, pasta_audio: str | None = None) -> list:
    """Move WAVs finalizados para PASTA_AUDIO e criptografa se ativo (FR-2.1/2.2)."""
    destinos = []
    pasta = pasta_audio if pasta_audio is not None else _config.PASTA_AUDIO
    os.makedirs(pasta, exist_ok=True)
    from crypto_storage import criptografar_wav

    for caminho in caminhos:
        if not caminho or not os.path.isfile(caminho):
            continue
        try:
            destino = os.path.join(pasta, os.path.basename(caminho))
            if os.path.abspath(caminho) != os.path.abspath(destino):
                if os.path.isfile(destino):
                    os.remove(destino)
                shutil.move(caminho, destino)
            if criptografar:
                destino = criptografar_wav(destino)
            destinos.append(destino)
        except Exception:
            logger.exception("Falha ao preservar áudio %s", caminho)
    return destinos


def rodar_diarizacao(transcritor, caminho_saida, caminho_wav) -> None:
    """Pós-processamento: separa falantes e escreve versão diarizada do .txt."""
    import numpy as np

    transcritor.diarizando = True
    try:
        if not transcritor._segmentos:
            transcritor.on_status("Sem segmentos para diarizar.")
            return

        transcritor.on_status("Iniciando separação de vozes (pós-processamento)...")
        try:
            from diarizador import diarizar

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
                caminho_mic_wav=caminho_mic,
                limiar_rms_mic=LIMIAR_RMS_MIC,
                eventos_meet=transcritor.eventos_meet,
                vozes_conhecidas=vozes_conhecidas,
                retornar_centroides=True,
            )
            transcritor._centroides_por_rotulo_ultima = centroides
        except Exception as e:
            transcritor.on_status(f"Erro na diarização: {e}")
            logger.exception("Erro na diarização")
            return

        base, ext = os.path.splitext(caminho_saida)
        caminho_diar = f"{base}_diarizado{ext}"
        linhas = [
            f"=== Transcricao diarizada em {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n\n"
        ]
        for rotulo, start, end, texto in resultado:
            mm_ss_start = f"{int(start // 60):02d}:{int(start % 60):02d}"
            mm_ss_end = f"{int(end // 60):02d}:{int(end % 60):02d}"
            linhas.append(f"[{rotulo} {mm_ss_start}-{mm_ss_end}] {texto}\n")
        linhas.append("\n=== Fim ===\n")
        texto_diar = "".join(linhas)
        if transcritor.criptografar:
            from crypto_storage import salvar_transcricao

            salvar_transcricao(caminho_diar, texto_diar)
        else:
            with open(caminho_diar, "w", encoding="utf-8") as f:
                f.write(texto_diar)

        transcritor.on_status(f"Diarização concluída: {os.path.basename(caminho_diar)}")
    finally:
        transcritor.diarizando = False
        # Usa método do Transcritor (respeita PASTA_AUDIO monkeypatch nos testes)
        transcritor._preservar_audios(
            caminho_wav, getattr(transcritor, "_caminho_wav_mic_salvo", None)
        )
