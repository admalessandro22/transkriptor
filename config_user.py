# -*- coding: utf-8 -*-
"""Acesso centralizado a config_user.json (FR-6.5, NFR-6.1).

Threading.Lock + escrita atômica (tmp + os.replace).
Único módulo de produção autorizado a abrir o arquivo.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading

from config import CONFIG_USER_FILE

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def carregar() -> dict:
    """Lê config_user.json. Retorna dict vazio se não existir ou for inválido."""
    with _lock:
        return _carregar_sem_lock()


def _carregar_sem_lock() -> dict:
    try:
        with open(CONFIG_USER_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except Exception:
        return {}


def salvar(cfg: dict) -> None:
    """Grava o dict inteiro de forma atômica (tmp + os.replace)."""
    if not isinstance(cfg, dict):
        raise TypeError("cfg deve ser dict")
    with _lock:
        _salvar_sem_lock(cfg)


def _salvar_sem_lock(cfg: dict) -> None:
    pasta = os.path.dirname(CONFIG_USER_FILE) or "."
    os.makedirs(pasta, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="config_user_", suffix=".tmp", dir=pasta)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_USER_FILE)
        tmp_path = None  # já movido
    except Exception:
        logger.exception("Erro ao salvar config_user")
        raise
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def atualizar(**kv) -> dict:
    """Mescla chaves em config_user.json e devolve o dict resultante."""
    with _lock:
        cfg = _carregar_sem_lock()
        cfg.update(kv)
        _salvar_sem_lock(cfg)
        return dict(cfg)
