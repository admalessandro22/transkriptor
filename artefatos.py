"""Referências verificáveis para artefatos persistidos do Transkriptor."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactRef:
    relative_path: str
    format: str
    schema_version: int
    sha256: str
    size_bytes: int


def sha256_arquivo(caminho: Path) -> str:
    """Calcula hash sem materializar o artefato inteiro em memória."""
    digest = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _relativo_validado(caminho: Path, raiz: Path) -> str:
    raiz_resolvida = Path(raiz).resolve(strict=True)
    caminho_resolvido = Path(caminho).resolve(strict=True)
    if not caminho_resolvido.is_file() or not caminho_resolvido.is_relative_to(
        raiz_resolvida
    ):
        raise ValueError("artefato deve ficar dentro da raiz validada")
    return caminho_resolvido.relative_to(raiz_resolvida).as_posix()


def criar_referencia(
    caminho: Path,
    raiz: Path,
    *,
    format: str,
    schema_version: int,
) -> ArtifactRef:
    if not isinstance(format, str) or not format:
        raise ValueError("formato de artefato inválido")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise ValueError("versão de artefato inválida")
    if schema_version < 1:
        raise ValueError("versão de artefato inválida")
    caminho_resolvido = Path(caminho).resolve(strict=True)
    relativo = _relativo_validado(caminho_resolvido, Path(raiz))
    return ArtifactRef(
        relative_path=relativo,
        format=format,
        schema_version=schema_version,
        sha256=sha256_arquivo(caminho_resolvido),
        size_bytes=caminho_resolvido.stat().st_size,
    )


def referencia_integra(referencia: ArtifactRef, raiz: Path) -> bool:
    """Confere path, tamanho e hash sem aceitar saída fora da raiz."""
    if not isinstance(referencia, ArtifactRef):
        return False
    if (
        not referencia.relative_path
        or not isinstance(referencia.format, str)
        or not referencia.format
        or Path(referencia.relative_path).is_absolute()
        or isinstance(referencia.schema_version, bool)
        or not isinstance(referencia.schema_version, int)
        or referencia.schema_version < 1
        or isinstance(referencia.size_bytes, bool)
        or not isinstance(referencia.size_bytes, int)
        or referencia.size_bytes < 0
        or len(referencia.sha256) != 64
        or any(caractere not in "0123456789abcdef" for caractere in referencia.sha256)
    ):
        return False
    try:
        raiz_resolvida = Path(raiz).resolve(strict=True)
        caminho = (raiz_resolvida / referencia.relative_path).resolve(strict=True)
    except (OSError, ValueError):
        return False
    if not caminho.is_file() or not caminho.is_relative_to(raiz_resolvida):
        return False
    try:
        return (
            caminho.stat().st_size == referencia.size_bytes
            and sha256_arquivo(caminho) == referencia.sha256
        )
    except OSError:
        return False
