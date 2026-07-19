#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve o caminho de pythonw.exe (prefere .venv do projeto)."""
import os
import sys
from pathlib import Path


def resolver_pythonw(base: Path | None = None) -> str:
    root = base or Path(__file__).resolve().parent.parent
    venv_w = root / ".venv" / "Scripts" / "pythonw.exe"
    if venv_w.is_file():
        return str(venv_w)
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        return exe
    if exe.lower().endswith("python.exe"):
        candidato = exe[:-10] + "pythonw.exe"
        if os.path.isfile(candidato):
            return candidato
        return candidato
    return exe.replace("python.exe", "pythonw.exe").replace("Python.exe", "pythonw.exe")


if __name__ == "__main__":
    path = resolver_pythonw()
    if not path.lower().endswith("pythonw.exe"):
        sys.exit(1)
    print(path)