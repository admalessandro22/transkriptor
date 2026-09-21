#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve o caminho de pythonw.exe (prefere .venv do projeto)."""
import os
import sys
from pathlib import Path


def resolver_pythonw(base: Path | None = None) -> str:
    caminho, _motivo = resolver_com_motivo(base)
    return caminho or ""


def resolver_com_motivo(base: Path | None = None) -> tuple[str | None, str]:
    """Resolve pythonw do MESMO venv; nunca mistura venv incompleto com sistema."""
    root = base or Path(__file__).resolve().parent.parent
    venv_dir = root / ".venv"
    venv_w = venv_dir / "Scripts" / "pythonw.exe"
    if venv_w.is_file():
        return str(venv_w), "venv"
    if venv_dir.is_dir():
        return None, "venv incompleto: rode instalar.bat (sem fallback silencioso)"
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe") and os.path.isfile(exe):
        return exe, "sistema"
    if exe.lower().endswith("python.exe"):
        candidato = exe[:-10] + "pythonw.exe"
        if os.path.isfile(candidato):
            return candidato, "sistema"
    return None, "Python não encontrado: rode instalar.bat"


if __name__ == "__main__":
    path, _motivo = resolver_com_motivo()
    if not (path or "").lower().endswith("pythonw.exe"):
        print(_motivo)
        sys.exit(1)
    print(path)