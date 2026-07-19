# -*- coding: utf-8 -*-
"""Criptografia em repouso — AES-256-GCM + DPAPI Windows (FR-3.*, SEC-8/9)."""
from __future__ import annotations

import base64
import json
import logging
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import CONFIG_USER_FILE, PASTA_TRANSCRICOES

logger = logging.getLogger(__name__)

MAGIC_HEADER = b"TKPT1"
NONCE_SIZE = 12
KEY_SIZE = 32
MSG_ERRO_LEITURA = "Não foi possível ler o arquivo. Abra pelo Transkriptor."

_chave_mestra: bytes | None = None


class ErroDescriptografia(Exception):
    """Falha de decrypt sem vazar detalhes do ciphertext (SEC-9)."""


def _carregar_config() -> dict:
    try:
        with open(CONFIG_USER_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _salvar_config(cfg: dict) -> None:
    with open(CONFIG_USER_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _dpapi_protect(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    in_buf = ctypes.create_string_buffer(data)
    in_blob = DATA_BLOB(len(data), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptProtectData falhou")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    in_buf = ctypes.create_string_buffer(data)
    in_blob = DATA_BLOB(len(data), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptUnprotectData falhou")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def criptografia_ativa() -> bool:
    return _carregar_config().get("criptografar_transcricoes", True)


def garantir_chave_mestra() -> bool:
    """Gera ou carrega chave mestra protegida por DPAPI. Retorna False se indisponível."""
    global _chave_mestra
    if _chave_mestra is not None:
        return True
    cfg = _carregar_config()
    blob_b64 = cfg.get("chave_dpapi")
    if blob_b64:
        try:
            protegido = base64.b64decode(blob_b64.encode("ascii"))
            _chave_mestra = _dpapi_unprotect(protegido)
            if len(_chave_mestra) == KEY_SIZE:
                return True
            logger.error("Chave DPAPI com tamanho inválido; criptografia indisponível.")
        except Exception:
            logger.error(
                "Não foi possível abrir chave DPAPI existente; dados antigos permanecem intactos.",
                exc_info=True,
            )
        _chave_mestra = None
        return False
    try:
        _chave_mestra = secrets.token_bytes(KEY_SIZE)
        protegido = _dpapi_protect(_chave_mestra)
        cfg["chave_dpapi"] = base64.b64encode(protegido).decode("ascii")
        _salvar_config(cfg)
        return True
    except Exception:
        logger.error("DPAPI indisponível; criptografia desativada.", exc_info=True)
        _chave_mestra = None
        return False


def chave_disponivel() -> bool:
    return garantir_chave_mestra()


def _exigir_chave() -> bytes:
    if not garantir_chave_mestra() or _chave_mestra is None:
        raise ErroDescriptografia(MSG_ERRO_LEITURA)
    return _chave_mestra


def criptografar_bytes(plano: bytes) -> bytes:
    chave = _exigir_chave()
    nonce = secrets.token_bytes(NONCE_SIZE)
    ciphertext = AESGCM(chave).encrypt(nonce, plano, None)
    return MAGIC_HEADER + nonce + ciphertext


def descriptografar_bytes(cifrado: bytes) -> bytes:
    if not cifrado.startswith(MAGIC_HEADER):
        raise ErroDescriptografia(MSG_ERRO_LEITURA)
    corpo = cifrado[len(MAGIC_HEADER) :]
    if len(corpo) < NONCE_SIZE + 16:
        raise ErroDescriptografia(MSG_ERRO_LEITURA)
    nonce = corpo[:NONCE_SIZE]
    ciphertext = corpo[NONCE_SIZE:]
    try:
        return AESGCM(_exigir_chave()).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ErroDescriptografia(MSG_ERRO_LEITURA) from exc


def salvar_bytes_arquivo(caminho: str, plano: bytes) -> None:
    path = Path(caminho)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(criptografar_bytes(plano))


def ler_bytes_arquivo(caminho: str) -> bytes:
    try:
        return descriptografar_bytes(Path(caminho).read_bytes())
    except ErroDescriptografia:
        raise
    except Exception as exc:
        raise ErroDescriptografia(MSG_ERRO_LEITURA) from exc


def salvar_transcricao(caminho: str, texto: str) -> None:
    salvar_bytes_arquivo(caminho, texto.encode("utf-8"))


def ler_transcricao(nome_arquivo: str, pasta: str | None = None) -> str:
    base = pasta or PASTA_TRANSCRICOES
    caminho = os.path.join(base, nome_arquivo)
    if nome_arquivo.endswith(".tkpt"):
        return ler_bytes_arquivo(caminho).decode("utf-8")
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def extensao_transcricao() -> str:
    return ".tkpt" if criptografia_ativa() and chave_disponivel() else ".txt"


def nome_base_transcricao(timestamp: str | None = None) -> str:
    import datetime

    ts = timestamp or datetime.datetime.now().strftime("%Y-%m-%d_%Hh%M")
    return f"transcricao_{ts}"


def caminho_transcricao_novo(pasta: str, diarizado: bool = False, criptografar: bool | None = None) -> str:
    base = nome_base_transcricao()
    if diarizado:
        base += "_diarizado"
    if criptografar is None:
        ext = extensao_transcricao()
    else:
        ext = ".tkpt" if criptografar and chave_disponivel() else ".txt"
    return os.path.join(pasta, base + ext)


def _backup_txt_na_migracao() -> bool:
    return bool(_carregar_config().get("backup_txt_na_migracao", False))


def _tkpt_valido(caminho: Path) -> bool:
    try:
        descriptografar_bytes(caminho.read_bytes())
        return True
    except Exception:
        return False


def _nome_migracao_sem_colisao(base_txt: Path) -> Path | None:
    """Retorna destino .tkpt ou None se .tkpt válido já existe (não sobrescrever)."""
    candidato = base_txt.with_suffix(".tkpt")
    if not candidato.is_file():
        return candidato
    if _tkpt_valido(candidato):
        return None
    n = 1
    while True:
        alternativo = base_txt.parent / f"{base_txt.stem}_migrado_{n:03d}.tkpt"
        if not alternativo.is_file():
            return alternativo
        n += 1


def _remover_txt_pos_migracao(arquivo: Path) -> None:
    if _backup_txt_na_migracao():
        arquivo.rename(arquivo.with_suffix(arquivo.suffix + ".bak"))
    else:
        arquivo.unlink()


def migrar_txt_legacy(pasta: str) -> int:
    """Converte `.txt` legados para `.tkpt` na primeira ativação (FR-3.6)."""
    if not chave_disponivel():
        return 0
    destino = Path(pasta)
    if not destino.is_dir():
        return 0
    migrados = 0
    for arquivo in sorted(destino.glob("*.txt")):
        if arquivo.name.endswith(".txt.bak"):
            continue
        try:
            alvo = _nome_migracao_sem_colisao(arquivo)
            if alvo is None:
                _remover_txt_pos_migracao(arquivo)
                continue
            texto = arquivo.read_text(encoding="utf-8")
            salvar_transcricao(str(alvo), texto)
            _remover_txt_pos_migracao(arquivo)
            migrados += 1
        except Exception:
            logger.warning("Falha ao migrar %s", arquivo.name, exc_info=True)
    return migrados


def migrar_vozes_legacy(
    caminho_npz: str,
    caminho_enc_perfil: str,
    caminho_json: str,
    caminho_enc_vozes: str,
) -> int:
    """Migra perfil e vozes legados em plaintext para `.enc` (FR-3.8)."""
    if not chave_disponivel():
        return 0
    migrados = 0
    npz = Path(caminho_npz)
    enc_perfil = Path(caminho_enc_perfil)
    if npz.is_file():
        try:
            if enc_perfil.is_file() and _tkpt_valido(enc_perfil):
                npz.unlink()
            else:
                salvar_bytes_arquivo(str(enc_perfil), npz.read_bytes())
                npz.unlink()
                migrados += 1
        except Exception:
            logger.warning("Falha ao migrar %s", npz.name, exc_info=True)
    json_path = Path(caminho_json)
    enc_vozes = Path(caminho_enc_vozes)
    if json_path.is_file():
        try:
            if enc_vozes.is_file() and _tkpt_valido(enc_vozes):
                json_path.unlink()
            else:
                salvar_bytes_arquivo(str(enc_vozes), json_path.read_bytes())
                json_path.unlink()
                migrados += 1
        except Exception:
            logger.warning("Falha ao migrar %s", json_path.name, exc_info=True)
    return migrados


def perfil_existe(caminho_npz: str, caminho_enc: str) -> bool:
    return os.path.isfile(caminho_enc) or os.path.isfile(caminho_npz)