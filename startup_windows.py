# -*- coding: utf-8 -*-
"""Atalho de inicialização com o Windows (shell:Startup).

Reutiliza `scripts/criar_atalho_desktop.ps1` com destino parametrizado (FR-8.2).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

from config import BASE_DIR, ICONE_FILE

logger = logging.getLogger(__name__)

STARTUP_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    "Microsoft",
    "Windows",
    "Start Menu",
    "Programs",
    "Startup",
)
ATALHO_STARTUP = os.path.join(STARTUP_DIR, "transkriptor.lnk")
SCRIPT_ATALHO = os.path.join(BASE_DIR, "scripts", "criar_atalho_desktop.ps1")


def startup_ativo(caminho: str = ATALHO_STARTUP) -> bool:
    """Retorna True se o atalho de startup existe."""
    return os.path.isfile(caminho)


def _pythonw() -> str:
    return sys.executable.replace("python.exe", "pythonw.exe")


def criar_atalho_startup(
    destino: str = ATALHO_STARTUP,
    pythonw: str | None = None,
    aplicativo: str | None = None,
    icone: str | None = None,
) -> bool:
    """Cria atalho no shell:startup via PS1 parametrizado."""
    try:
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        pyw = pythonw or _pythonw()
        app = aplicativo or os.path.join(BASE_DIR, "transkriptor.pyw")
        ico = icone or ICONE_FILE
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            SCRIPT_ATALHO,
            "-Pythonw",
            pyw,
            "-Aplicativo",
            app,
            "-Icone",
            ico,
            "-Destino",
            destino,
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=15, text=True)
        if r.returncode != 0:
            logger.error(
                "Erro ao criar atalho de startup (code=%s): %s %s",
                r.returncode,
                r.stdout,
                r.stderr,
            )
            return False
        ok = os.path.isfile(destino)
        if ok:
            logger.info("Atalho de startup criado.")
        return ok
    except Exception as e:
        logger.error("Erro ao criar atalho de startup: %s", e)
        return False


def remover_atalho_startup(destino: str = ATALHO_STARTUP) -> bool:
    """Remove o atalho de startup."""
    try:
        if os.path.isfile(destino):
            os.remove(destino)
            logger.info("Atalho de startup removido.")
        return True
    except Exception as e:
        logger.error("Erro ao remover atalho de startup: %s", e)
        return False
