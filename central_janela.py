# -*- coding: utf-8 -*-
"""Abertura da Central no navegador (UX-14.B1, DP-14-06).

Prefere uma janela de app do Edge ou do Chrome (sem barra de endereço);
cai para a aba padrão quando não há executável ou a chamada falha.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import webbrowser

logger = logging.getLogger(__name__)

_CANDIDATOS_NAVEGADOR_APP = (
    ("msedge", r"Microsoft\Edge\Application\msedge.exe"),
    ("chrome", r"Google\Chrome\Application\chrome.exe"),
)


def _executavel_navegador_app() -> str | None:
    """UX-14.B1 (DP-14-06): Edge ou Chrome para abrir a Central em janela de app."""
    if os.environ.get("TRANSKRIPTOR_JANELA_APP", "1") == "0":
        return None
    raizes = [os.environ.get(v) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    for nome, relativo in _CANDIDATOS_NAVEGADOR_APP:
        encontrado = shutil.which(nome)
        if encontrado:
            return encontrado
        for raiz in raizes:
            if raiz and os.path.isfile(os.path.join(raiz, relativo)):
                return os.path.join(raiz, relativo)
    return None


def _abrir_navegador(url: str, token: str, pagina: str = "") -> None:
    """Abre a Central em janela de app quando há Edge/Chrome; senão, na aba padrão."""
    destino = f"{url}?token={token}" + (f"&next={pagina}" if pagina else "")
    executavel = _executavel_navegador_app()
    if executavel:
        try:
            subprocess.Popen([executavel, f"--app={destino}", "--window-size=1366,860"])
            return
        except OSError:
            logger.warning("Janela de app indisponível; abrindo no navegador padrão.")
    webbrowser.open(destino)
