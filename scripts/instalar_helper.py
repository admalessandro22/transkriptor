# -*- coding: utf-8 -*-
"""Pré-checagens testáveis do instalador (FR-7.*)."""
from __future__ import annotations

import os
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


def combinacao_valida(selecao: dict) -> tuple[bool, str]:
    """Pré-checagem de conjunto (T-13.G1): incompatível reprova com motivo claro."""
    torch_cuda = bool(selecao.get("torch_cuda"))
    tem_gpu = bool(selecao.get("tem_gpu"))
    if torch_cuda and not tem_gpu:
        return False, "ERRO: rota torch CUDA sem GPU NVIDIA detectada — use a rota CPU"
    return True, "OK combinação de dependências"


def _rota_detectada() -> str:
    return "cuda" if tem_gpu_nvidia() else "cpu"


def processo_ativo(runner: Runner | None = None) -> bool:
    """Detecta app/gravação em curso via tasklist (desinstalador aborta)."""
    runner = runner or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True))
    try:
        r = runner(["tasklist", "/FO", "CSV", "/NH"])
    except Exception:
        return False
    if r.returncode != 0:
        return False
    texto = ((r.stdout or "") + "\n" + (r.stderr or "")).lower()
    return ("transkriptor.pyw" in texto) or ("processador_reuniao" in texto)


def alvos_desinstalacao() -> dict:
    """Alvos exatos do desinstalador; dados nunca listados aqui (preservados)."""
    import os as _os

    perfil = _os.environ.get("USERPROFILE", "")
    appdata = _os.environ.get("APPDATA", "")
    return {
        "atalhos": [
            os.path.join(perfil, "Desktop", "Transkriptor.lnk"),
            os.path.join(perfil, "OneDrive", "Desktop", "Transkriptor.lnk"),
            os.path.join(
                appdata, "Microsoft", "Windows", "Start Menu", "Programs",
                "Startup", "transkriptor.lnk",
            ),
        ],
        "venv": os.path.join(os.getcwd(), ".venv"),
    }


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if not argv or argv[0] != "--check":
        print("Uso: instalar_helper.py --check python|gpu|ollama|torch|deps")
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
    if oque == "deps":
        rota = ""
        for i, parte in enumerate(argv):
            if parte == "--rota" and i + 1 < len(argv):
                rota = argv[i + 1]
        if rota not in ("cpu", "cuda"):
            print("ERRO: informe --rota cpu|cuda")
            return 2
        ok, msg = combinacao_valida({"torch_cuda": rota == "cuda", "tem_gpu": tem_gpu_nvidia()})
        print(f"{msg} (rota {rota})")
        return 0 if ok else 1
    if oque == "processo":
        if processo_ativo():
            print("ERRO: Transkriptor em execução ou gravando — encerre antes de desinstalar")
            return 1
        print("OK nenhum processo do Transkriptor em execução")
        return 0
    print("ERRO: check desconhecido")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
