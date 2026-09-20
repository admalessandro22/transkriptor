# -*- coding: utf-8 -*-
"""Política única de proteção e falha explícita (T-13.E1)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping

import config_user

logger = logging.getLogger(__name__)

CHAVE_MODO = "protection_mode"
DIR_RESTRITO = "restrito"
MAGIC_CIFRADO = b"TKPT1"


class ProtectionMode(StrEnum):
    COMPATIBLE = "compatible"
    PROTECTED = "protected"


class ProtectionState(StrEnum):
    PLAINTEXT_ALLOWED = "plaintext_allowed"
    PROTECTED = "protected"
    PROTECTION_PENDING = "protection_pending"
    UNREADABLE = "unreadable"


class ProtectionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtifactProtection:
    mode: ProtectionMode
    state: ProtectionState
    relative_path: str
    sha256: str


def resolve_initial_mode(existing_config: Mapping | None) -> ProtectionMode:
    """Instalação nova (sem config) inicia protegida; existente sem campo é compatível."""
    if existing_config is None:
        return ProtectionMode.PROTECTED
    valor = dict(existing_config).get(CHAVE_MODO)
    if valor == ProtectionMode.PROTECTED.value:
        return ProtectionMode.PROTECTED
    return ProtectionMode.COMPATIBLE


def _config_existe() -> bool:
    try:
        from config_user import CONFIG_USER_FILE

        return Path(CONFIG_USER_FILE).is_file()
    except Exception:  # noqa: BLE001
        return True


def modo_efetivo() -> ProtectionMode:
    if not _config_existe():
        return ProtectionMode.PROTECTED
    try:
        return resolve_initial_mode(config_user.carregar())
    except Exception:  # noqa: BLE001
        return ProtectionMode.COMPATIBLE


def _chave_ok() -> bool:
    try:
        from crypto_storage import chave_disponivel, criptografia_ativa

        return bool(criptografia_ativa()) and bool(chave_disponivel())
    except Exception:  # noqa: BLE001
        return False


def _parece_cifrado(caminho: Path) -> bool:
    nome = caminho.name.lower()
    if nome.endswith((".enc", ".tkpt", ".tks")):
        return True
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read(5) == MAGIC_CIFRADO
    except OSError:
        return False


def _sha(caminho: Path) -> str:
    from artefatos import sha256_arquivo

    return sha256_arquivo(caminho)


def protect_artifact(path: Path, mode: ProtectionMode) -> ArtifactProtection:
    """Garante proteção do artefato sem fallback silencioso.

    Já cifrado permanece cifrado (nunca rebaixado). Em modo protegido,
    plaintext é cifrado com validação; qualquer falha move o original para
    área restrita e devolve `PROTECTION_PENDING` — a única cópia é preservada.
    """
    from crypto_storage import ler_bytes_arquivo, salvar_bytes_arquivo

    caminho = Path(path)
    if not caminho.is_file():
        raise ValueError("artefato inexistente")
    if _parece_cifrado(caminho):
        if _chave_ok():
            try:
                ler_bytes_arquivo(str(caminho))
                return ArtifactProtection(mode, ProtectionState.PROTECTED, caminho.name, _sha(caminho))
            except Exception:  # noqa: BLE001
                pass
        return ArtifactProtection(mode, ProtectionState.UNREADABLE, caminho.name, _sha(caminho))
    if mode == ProtectionMode.COMPATIBLE:
        return ArtifactProtection(mode, ProtectionState.PLAINTEXT_ALLOWED, caminho.name, _sha(caminho))
    if not _chave_ok():
        return _para_area_restrita(caminho, mode)
    destino = caminho.with_name(caminho.name + ".enc")
    try:
        salvar_bytes_arquivo(str(destino), caminho.read_bytes())
        if ler_bytes_arquivo(str(destino)) != caminho.read_bytes():
            raise ValueError("validação de cifra divergente")
        caminho.unlink()
        return ArtifactProtection(mode, ProtectionState.PROTECTED, destino.name, _sha(destino))
    except Exception:  # noqa: BLE001 — nunca apaga o original em falha
        logger.warning("Falha ao proteger %s; preservado em área restrita", caminho.name)
        try:
            if destino.is_file():
                destino.unlink()
        except OSError:
            pass
        return _para_area_restrita(caminho, mode)


def _para_area_restrita(caminho: Path, mode: ProtectionMode) -> ArtifactProtection:
    destino_dir = caminho.parent / DIR_RESTRITO
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / caminho.name
    indice = 2
    while destino.exists():
        destino = destino_dir / f"{caminho.stem}_{indice:02d}{caminho.suffix}"
        indice += 1
    caminho.replace(destino)
    return ArtifactProtection(mode, ProtectionState.PROTECTION_PENDING, destino.name, _sha(destino))


def inventariar_migracao(pasta: Path) -> tuple[list[str], list[str]]:
    """Lista (candidatos .txt sem .tkpt, preservados). Não remove nada."""
    base = Path(pasta)
    candidatos, preservados = [], []
    if not base.is_dir():
        return candidatos, preservados
    for txt in sorted(base.glob("*.txt")):
        if txt.name.endswith(".txt.bak"):
            continue
        tkpt = txt.with_suffix(".tkpt")
        if tkpt.is_file():
            preservados.append(tkpt.name)
        else:
            candidatos.append(txt.name)
    return candidatos, preservados


def aplicar_migracao_confirmada(
    pasta: Path,
    candidatos: list[str],
    confirmados: list[str],
    dry_run: bool = True,
) -> list[str]:
    """Remove só a interseção confirmada; dry_run (padrão) não remove."""
    alvos = [n for n in candidatos if n in set(confirmados or ())]
    if dry_run:
        return []
    removidos = []
    for nome in alvos:
        alvo = Path(pasta) / nome
        try:
            if alvo.is_file():
                alvo.unlink()
                removidos.append(nome)
        except OSError:
            logger.warning("Falha ao remover %s", nome, exc_info=True)
    return removidos
