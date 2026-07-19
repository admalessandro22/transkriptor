# -*- coding: utf-8 -*-
"""Retenção de áudios de reunião (FR-2.3)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from config import RETENCAO_AUDIO_DIAS

logger = logging.getLogger(__name__)


def _nome_base_audio(nome_arquivo: str) -> str:
    """`transcricao_..._audio.wav` / `.wav.enc` → `transcricao_...`."""
    nome = nome_arquivo
    if nome.endswith(".wav.enc"):
        nome = nome[: -len(".wav.enc")]
    elif nome.endswith(".wav"):
        nome = nome[: -len(".wav")]
    if nome.endswith("_audio"):
        nome = nome[: -len("_audio")]
    if nome.endswith("_mic"):
        nome = nome[: -len("_mic")]
    return nome


def _existe_transcricao(pasta_transcricoes: Path, base: str) -> bool:
    if not pasta_transcricoes.is_dir():
        return False
    for ext in (".txt", ".tkpt"):
        if (pasta_transcricoes / f"{base}{ext}").is_file():
            return True
        if (pasta_transcricoes / f"{base}_diarizado{ext}").is_file():
            return True
    # qualquer arquivo cujo stem comece com o base (ex. renomeações)
    for f in pasta_transcricoes.iterdir():
        if not f.is_file():
            continue
        if f.suffix not in (".txt", ".tkpt"):
            continue
        stem = f.stem
        if stem == base or stem.startswith(base + "_"):
            return True
    return False


def limpar_audios_vencidos(
    pasta_audio: str,
    pasta_transcricoes: str,
    dias: int = RETENCAO_AUDIO_DIAS,
    agora: datetime | None = None,
) -> tuple[list[str], list[str]]:
    """Remove áudios além da retenção **somente se** houver transcrição.

    Returns:
        (removidos, orfaos_vencidos): órfãos vencidos sem transcrição são mantidos
        e reportados para notificação.
    """
    agora = agora or datetime.now()
    limite = agora - timedelta(days=dias)
    pasta_a = Path(pasta_audio)
    pasta_t = Path(pasta_transcricoes)
    removidos: list[str] = []
    orfaos: list[str] = []
    if not pasta_a.is_dir():
        return removidos, orfaos

    candidatos: list[Path] = []
    for p in pasta_a.iterdir():
        if not p.is_file():
            continue
        n = p.name.lower()
        if n.endswith(".wav") or n.endswith(".wav.enc"):
            candidatos.append(p)

    for path in sorted(candidatos):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if mtime > limite:
            continue
        base = _nome_base_audio(path.name)
        if _existe_transcricao(pasta_t, base):
            try:
                path.unlink()
                removidos.append(str(path))
            except OSError:
                logger.warning("Falha ao remover áudio vencido %s", path.name, exc_info=True)
        else:
            orfaos.append(str(path))
    return removidos, orfaos
