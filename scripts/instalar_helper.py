# -*- coding: utf-8 -*-
"""Pré-checagens testáveis do instalador (FR-7.*)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable


Runner = Callable[[list[str]], subprocess.CompletedProcess]


def python_compativel(version_info=None) -> tuple[bool, str]:
    vi = version_info or sys.version_info
    if vi.major > 3 or (vi.major == 3 and vi.minor >= 12):
        return True, f"OK Python {vi.major}.{vi.minor}"
    return False, f"ERRO: Python 3.12+ necessário (encontrado {vi.major}.{vi.minor})"


def tem_gpu_nvidia(runner: Runner | None = None) -> bool:
    runner = runner or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True))
    try:
        r = runner(["nvidia-smi", "-L"])
        return r.returncode == 0 and bool((r.stdout or "").strip())
    except Exception:
        return False


def ollama_status(runner: Runner | None = None) -> tuple[str, str]:
    """Retorna (codigo, mensagem) codigo in ok|aviso|erro."""
    runner = runner or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True))
    try:
        r = runner(["ollama", "list"])
    except Exception:
        return "aviso", "AVISO: Ollama não encontrado (assistente opcional)"
    if r.returncode != 0:
        return "aviso", "AVISO: Ollama não responde"
    out = (r.stdout or "") + (r.stderr or "")
    # header + models
    linhas = [ln for ln in out.splitlines() if ln.strip() and not ln.lower().startswith("name")]
    if not linhas:
        return "aviso", "AVISO: Ollama sem modelos — sugestão: ollama pull llama3.1:8b"
    return "ok", "OK Ollama com modelos"


def comando_torch(tem_gpu: bool) -> list[str]:
    if tem_gpu:
        return [
            sys.executable,
            "-m",
            "pip",
            "install",
            "torch",
            "torchaudio",
            "--index-url",
            "https://download.pytorch.org/whl/cu128",
        ]
    return [sys.executable, "-m", "pip", "install", "torch", "torchaudio"]


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if not argv or argv[0] != "--check":
        print("Uso: instalar_helper.py --check python|gpu|ollama|torch")
        return 2
    oque = argv[1] if len(argv) > 1 else ""
    if oque == "python":
        ok, msg = python_compativel()
        print(msg)
        return 0 if ok else 1
    if oque == "gpu":
        if tem_gpu_nvidia():
            print("OK GPU NVIDIA")
            return 0
        print("AVISO: GPU NVIDIA não detectada — usará torch CPU")
        return 0
    if oque == "ollama":
        _c, msg = ollama_status()
        print(msg)
        return 0
    if oque == "torch":
        gpu = tem_gpu_nvidia()
        cmd = comando_torch(gpu)
        print(" ".join(cmd))
        return 0
    print("ERRO: check desconhecido")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
