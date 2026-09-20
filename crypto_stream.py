# -*- coding: utf-8 -*-
"""Áudio longo protegido TKAS/1 sobre PyNaCl SecretStream (T-13.E1).

Layout: magic `TKAS` (4B) + versão `0x01` + chunk size u32 LE (fixo 1 MiB) +
header SecretStream (32B) + ciphertexts consecutivos (último `TAG_FINAL`,
demais `TAG_MESSAGE`). Associated data por chunk: cabeçalho de 9B + índice
u64 LE. Chave de stream derivada da mestra via HKDF-SHA256 (não persistida).
Primitiva: bindings PyNaCl de `crypto_secretstream_xchacha20poly1305` —
nenhuma primitiva reinventada. Sem PyNaCl, modo protegido bloqueia explícito.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Iterator

from artefatos import ArtifactRef, sha256_arquivo

MAGIC = b"TKAS"
VERSAO = 0x01
TAMANHO_CHUNK = 1_048_576
INFO_DERIVACAO = b"transkriptor-audio-secretstream-v1"


class ErroTKAS(ValueError):
    """Falha de autenticação, truncamento, reordenação ou formato TKAS."""


class BibliotecaIndisponivel(RuntimeError):
    """PyNaCl/libsodium não carregou: áudio longo protegido bloqueado."""


def _ligacoes():
    try:
        from nacl.bindings import (
            crypto_secretstream_xchacha20poly1305_ABYTES as ABYTES,
            crypto_secretstream_xchacha20poly1305_HEADERBYTES as HEADERBYTES,
            crypto_secretstream_xchacha20poly1305_MESSAGEBYTES_MAX as MAXBYTES,
            crypto_secretstream_xchacha20poly1305_TAG_FINAL as TAG_FINAL,
            crypto_secretstream_xchacha20poly1305_TAG_MESSAGE as TAG_MESSAGE,
            crypto_secretstream_xchacha20poly1305_init_pull as init_pull,
            crypto_secretstream_xchacha20poly1305_init_push as init_push,
            crypto_secretstream_xchacha20poly1305_pull as pull,
            crypto_secretstream_xchacha20poly1305_push as push,
            crypto_secretstream_xchacha20poly1305_state as make_state,
        )
    except ImportError as exc:
        raise BibliotecaIndisponivel(
            "PyNaCl/libsodium indisponível: áudio longo protegido bloqueado"
        ) from exc
    return {
        "ABYTES": ABYTES,
        "HEADERBYTES": HEADERBYTES,
        "MAXBYTES": MAXBYTES,
        "TAG_FINAL": TAG_FINAL,
        "TAG_MESSAGE": TAG_MESSAGE,
        "init_pull": init_pull,
        "init_push": init_push,
        "pull": pull,
        "push": push,
        "make_state": make_state,
    }


def _chave_stream(master_key: bytes) -> bytes:
    if not isinstance(master_key, (bytes, bytearray)) or len(master_key) != 32:
        raise ErroTKAS("chave mestra inválida (exigidos 32 bytes)")
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=INFO_DERIVACAO,
    ).derive(bytes(master_key))


def _cabecalho_arquivo() -> bytes:
    return MAGIC + bytes((VERSAO,)) + TAMANHO_CHUNK.to_bytes(4, "little")


def _ad_chunk(caminho_ou_cabecalho, indice: int) -> bytes:
    if isinstance(caminho_ou_cabecalho, (bytes, bytearray)):
        cabecalho = bytes(caminho_ou_cabecalho)
    else:
        with open(str(caminho_ou_cabecalho), "rb") as arquivo:
            cabecalho = arquivo.read(9)
    if len(cabecalho) != 9:
        raise ErroTKAS("cabeçalho TKAS inválido")
    return cabecalho + int(indice).to_bytes(8, "little")


def encrypt_file(source: Path, destination: Path, master_key: bytes) -> ArtifactRef:
    """Cifra em blocos com escrita atômica e validação por leitura autenticada."""
    lig = _ligacoes()
    chave = _chave_stream(master_key)
    origem, destino = Path(source), Path(destination)
    if not origem.is_file():
        raise FileNotFoundError(str(origem))
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(
        prefix=f"{destino.stem}_", suffix=".tmp", dir=str(destino.parent)
    )
    try:
        estado = lig["make_state"]()
        cabeca_stream = lig["init_push"](estado, chave)
        with os.fdopen(fd, "wb") as saida:
            cabecalho = _cabecalho_arquivo()
            saida.write(cabecalho)
            saida.write(cabeca_stream)
            with open(origem, "rb") as entrada:
                indice = 0
                while True:
                    bloco = entrada.read(TAMANHO_CHUNK)
                    if not bloco:
                        if indice == 0:
                            saida.write(
                                lig["push"](
                                    estado, b"", _ad_chunk(cabecalho, 0), lig["TAG_FINAL"]
                                )
                            )
                        break
                    pos = entrada.tell()
                    ultimo = len(entrada.read(1)) == 0
                    entrada.seek(pos)
                    etiqueta = lig["TAG_FINAL"] if ultimo else lig["TAG_MESSAGE"]
                    saida.write(
                        lig["push"](estado, bloco, _ad_chunk(cabecalho, indice), etiqueta)
                    )
                    if ultimo:
                        break
                    indice += 1
            saida.flush()
            os.fsync(saida.fileno())
        temporario_path = Path(temporario)
        temporario = None
        # Validação por leitura autenticada antes de qualquer replace.
        list(iter_decrypt_file(temporario_path, master_key))
        os.replace(temporario_path, destino)
        return ArtifactRef(
            relative_path=destino.name,
            format="tks/1",
            schema_version=1,
            sha256=sha256_arquivo(destino),
            size_bytes=destino.stat().st_size,
        )
    finally:
        if temporario and os.path.isfile(temporario):
            try:
                os.remove(temporario)
            except OSError:
                pass


def iter_decrypt_file(path: Path, master_key: bytes) -> Iterator[bytes]:
    """Itera plaintext autenticado; qualquer falha aborta sem parcial válido."""
    lig = _ligacoes()
    chave = _chave_stream(master_key)
    caminho = Path(path)
    with open(caminho, "rb") as entrada:
        cabecalho = entrada.read(9)
        if len(cabecalho) != 9 or not cabecalho.startswith(MAGIC):
            raise ErroTKAS("magic TKAS ausente")
        if cabecalho[4] != VERSAO:
            raise ErroTKAS("versão TKAS não suportada")
        tamanho = int.from_bytes(cabecalho[5:9], "little")
        if tamanho <= 0 or tamanho > 64 * 1024 * 1024:
            raise ErroTKAS("chunk size TKAS inválido")
        cabeca_stream = entrada.read(lig["HEADERBYTES"])
        if len(cabeca_stream) != lig["HEADERBYTES"]:
            raise ErroTKAS("header SecretStream ausente")
        estado = lig["make_state"]()
        lig["init_pull"](estado, cabeca_stream, chave)
        indice = 0
        viu_final = False
        while True:
            cifra = entrada.read(tamanho + lig["ABYTES"])
            if not cifra:
                break
            try:
                plano, etiqueta = lig["pull"](estado, bytes(cifra), _ad_chunk(cabecalho, indice))
            except Exception as exc:
                raise ErroTKAS(f"chunk {indice} sem autenticação") from exc
            if viu_final:
                raise ErroTKAS("dados após tag final")
            if etiqueta == lig["TAG_FINAL"]:
                viu_final = True
            elif etiqueta != lig["TAG_MESSAGE"]:
                raise ErroTKAS(f"tag inesperada no chunk {indice}")
            yield bytes(plano)
            if viu_final:
                break
            indice += 1
        if not viu_final:
            raise ErroTKAS("tag final ausente (truncado)")
