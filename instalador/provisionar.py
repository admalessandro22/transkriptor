# -*- coding: utf-8 -*-
"""Provisionamento do instalador por usuário (T-15.E4 / FR-15.E4).

Chamado pelo Inno Setup com o `uv` embutido: não exige Python instalado nem
administrador. Cria `.venv` com Python 3.12 gerenciado pelo `uv`, aplica o
lockfile da rota (CPU ou CUDA, por `nvidia-smi`) **com hash obrigatório**,
registra o host de pareamento e escreve o que encontrou do Ollama para a
página final. Na desinstalação, remove o registro e preserva os dados.

    uv run --python 3.12 --no-project instalador\\provisionar.py [--rota auto|cpu|cuda]
    ... provisionar.py --detectar
    ... provisionar.py --desinstalar [--apagar-dados]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

ROTAS = ("cpu", "cuda")
DADOS_DO_USUARIO = ("transcricoes", "config_user.json", "_modelo_voz")


def escolher_rota(executar=subprocess.run) -> str:
    try:
        saida = executar(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=10).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return "cpu"
    return "cuda" if "GPU" in saida else "cpu"


def _python_venv(pasta: Path) -> Path:
    return Path(pasta) / ".venv" / "Scripts" / "python.exe"


def comandos(pasta: Path, rota: str, *, uv: str = "uv") -> list[list[str]]:
    if rota not in ROTAS:
        raise ValueError("rota de instalação inválida")
    pasta = Path(pasta)
    lock = pasta / "requirements" / f"requirements-{rota}.lock"
    sync = [uv, "pip", "sync", "--require-hashes", "--python", str(_python_venv(pasta))]
    if rota == "cuda":
        # O lock CUDA (índice do PyTorch + PyPI) foi gerado pelo pip, que escolhe
        # entre índices; o uv para no primeiro. O hash obrigatório impede troca.
        sync += ["--index-strategy", "unsafe-best-match"]
    return [[uv, "venv", "--python", "3.12", str(pasta / ".venv")], sync + [str(lock)]]


def detectar_json(deteccao) -> str:
    """Só estado, versão e nomes de modelos: nunca o caminho (tem o nome do usuário)."""
    return json.dumps({"estado": deteccao.estado, "versao": deteccao.versao,
                       "modelos": [m.id for m in deteccao.modelos]}, ensure_ascii=False)


def detectar_texto(deteccao=None) -> str:
    if deteccao is None:
        from detector_ollama import detectar_ollama

        deteccao = detectar_ollama()
    if deteccao.estado == "online":
        return (f"Ollama {deteccao.versao or ''} encontrado com {len(deteccao.modelos)} modelo(s). "
                "Você escolhe qual usar nos primeiros passos.")
    if deteccao.estado == "parado":
        return "Ollama instalado, mas fechado. Os primeiros passos oferecem abri-lo."
    return ("O Ollama não está instalado. Os primeiros passos mostram onde baixá-lo, "
            "ou você pode usar uma chave do OpenRouter.")


def _registrar(pasta: Path, python: str) -> None:
    from instalador.registrar_host import registrar

    registrar(pasta, python=python)


def provisionar(pasta: Path = RAIZ, *, rota: str | None = None, uv: str = "uv", executar=subprocess.run,
                registrar=_registrar, detectar=detectar_texto) -> str:
    pasta = Path(pasta)
    rota = rota if rota in ROTAS else escolher_rota()
    for comando in comandos(pasta, rota, uv=uv):
        executar(comando, check=True)
    registrar(pasta, str(_python_venv(pasta)))
    destino = pasta / "instalador" / "ollama-detectado.txt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(detectar(), encoding="utf-8")
    return rota


def _desregistrar() -> None:
    from instalador.registrar_host import desregistrar

    desregistrar()


def desinstalar(pasta: Path = RAIZ, *, apagar_dados: bool = False, desregistrar=_desregistrar) -> None:
    desregistrar()
    if not apagar_dados:
        return
    for nome in DADOS_DO_USUARIO:
        alvo = Path(pasta) / nome
        if alvo.is_dir():
            shutil.rmtree(alvo, ignore_errors=True)
        elif alvo.exists():
            alvo.unlink()


def main(argv: list[str]) -> int:
    if "--detectar" in argv:
        print(detectar_texto())
        return 0
    if "--desinstalar" in argv:
        desinstalar(apagar_dados="--apagar-dados" in argv)
        return 0
    rota = argv[argv.index("--rota") + 1] if "--rota" in argv else "auto"
    uv = argv[argv.index("--uv") + 1] if "--uv" in argv else "uv"
    print(f"Rota instalada: {provisionar(rota=rota, uv=uv)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
