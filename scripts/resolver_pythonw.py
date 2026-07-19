#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve o caminho de pythonw.exe da instalação Python atual."""
import sys


def resolver_pythonw():
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        return exe
    if exe.lower().endswith("python.exe"):
        candidato = exe[:-10] + "pythonw.exe"
        if candidato.lower().endswith("pythonw.exe"):
            return candidato
    return exe.replace("python.exe", "pythonw.exe").replace("Python.exe", "pythonw.exe")


if __name__ == "__main__":
    path = resolver_pythonw()
    if not path.lower().endswith("pythonw.exe"):
        sys.exit(1)
    print(path)