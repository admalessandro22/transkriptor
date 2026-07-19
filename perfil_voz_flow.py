# -*- coding: utf-8 -*-
"""Fluxo de cadastro/remoção do perfil de voz do usuário (FR-8.2)."""

from __future__ import annotations

import logging
import os
from typing import Callable

from config import (
    ARQUIVO_PERFIL_VOZ,
    ARQUIVO_PERFIL_VOZ_ENC,
    DURACAO_CADASTRO_SEG,
)

logger = logging.getLogger(__name__)


def apagar_arquivos_perfil(
    caminho_npz: str = ARQUIVO_PERFIL_VOZ,
    caminho_enc: str = ARQUIVO_PERFIL_VOZ_ENC,
) -> None:
    for caminho in (caminho_npz, caminho_enc):
        if os.path.isfile(caminho):
            os.remove(caminho)


def cadastrar_perfil_voz(
    *,
    duracao_seg: int = DURACAO_CADASTRO_SEG,
    caminho_npz: str = ARQUIVO_PERFIL_VOZ,
    caminho_enc: str = ARQUIVO_PERFIL_VOZ_ENC,
    on_status: Callable[[str], None] | None = None,
    notificar_fn: Callable[[str, str], None] | None = None,
) -> bool:
    """Grava mic, extrai embedding ECAPA e salva perfil. Retorna True se ok."""
    from identificador_voz import gravar_audio_microfone, perfil_de_chunks, salvar_perfil
    from diarizador import _carregar_encoder

    def _status(msg: str) -> None:
        if on_status:
            on_status(msg)

    def _toast(titulo: str, msg: str) -> None:
        if notificar_fn:
            notificar_fn(titulo, msg)

    _toast(
        "Transkriptor",
        f"Fale por {duracao_seg}s após o sinal. Leia um texto em voz alta.",
    )
    _status(f"Gravando perfil de voz ({duracao_seg}s)...")
    try:
        chunks = gravar_audio_microfone(duracao_seg)
        encoder = _carregar_encoder()
        embedding = perfil_de_chunks(encoder, chunks)
        if embedding is None:
            _toast("Transkriptor", "Erro: áudio insuficiente para cadastro.")
            _status("Erro no cadastro de voz.")
            return False
        os.makedirs(os.path.dirname(caminho_npz) or ".", exist_ok=True)
        salvar_perfil(embedding, caminho_npz, caminho_enc)
        _toast("Transkriptor", "Perfil de voz salvo.")
        _status("Perfil de voz salvo.")
        return True
    except Exception as e:
        logger.exception("Erro ao cadastrar voz")
        _toast("Transkriptor", f"Erro no cadastro: {e}")
        _status(f"Erro no cadastro de voz: {e}")
        return False


def ativar_identificacao_apos_cadastro(
    carregar_cfg: Callable[[], dict],
    salvar_cfg: Callable[[dict], None],
    rotulo_usuario: str,
    capturar_mic: bool,
) -> None:
    """Persiste preferências após cadastro bem-sucedido."""
    cfg = carregar_cfg()
    cfg["versao_config"] = 2
    cfg["identificar_minha_voz"] = True
    cfg["rotulo_usuario"] = rotulo_usuario
    cfg["capturar_mic"] = capturar_mic
    salvar_cfg(cfg)


def desativar_perfil_na_config(
    carregar_cfg: Callable[[], dict],
    salvar_cfg: Callable[[dict], None],
) -> None:
    cfg = carregar_cfg()
    cfg["identificar_minha_voz"] = False
    salvar_cfg(cfg)
