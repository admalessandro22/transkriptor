# -*- coding: utf-8 -*-
"""T-F7-01 — helper do instalador."""
import subprocess
from types import SimpleNamespace

from scripts.instalar_helper import (
    comando_torch,
    ollama_status,
    python_compativel,
    tem_gpu_nvidia,
)


def test_python_312_ok():
    ok, msg = python_compativel(SimpleNamespace(major=3, minor=12))
    assert ok
    assert "OK" in msg


def test_python_311_reprovado():
    ok, msg = python_compativel(SimpleNamespace(major=3, minor=11))
    assert not ok
    assert "3.12" in msg
    assert "ERRO" in msg


def test_gpu_presente_ausente():
    assert tem_gpu_nvidia(lambda cmd: SimpleNamespace(returncode=0, stdout="GPU 0: GTX\n"))
    assert not tem_gpu_nvidia(lambda cmd: SimpleNamespace(returncode=1, stdout=""))


def test_ollama_ramos():
    c, m = ollama_status(lambda cmd: (_ for _ in ()).throw(FileNotFoundError()))
    assert c == "aviso" and "Ollama" in m
    c, m = ollama_status(lambda cmd: SimpleNamespace(returncode=1, stdout="", stderr="x"))
    assert c == "aviso"
    c, m = ollama_status(
        lambda cmd: SimpleNamespace(returncode=0, stdout="NAME\nllama3.1:8b\n", stderr="")
    )
    assert c == "ok"


def test_comando_torch_gpu_cpu():
    g = comando_torch(True)
    assert "cu128" in " ".join(g)
    c = comando_torch(False)
    assert "cu128" not in " ".join(c)
