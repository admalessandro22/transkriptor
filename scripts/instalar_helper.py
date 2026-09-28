# -*- coding: utf-8 -*-
"""Pré-checagens testáveis do instalador (FR-7.*)."""
from __future__ import annotations

import os
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path
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


def versoes_torch_instaladas() -> tuple[str | None, str | None]:
    """Lê metadados sem carregar torch nem inicializar GPU."""
    def versao(nome: str) -> str | None:
        try:
            return metadata.version(nome)
        except metadata.PackageNotFoundError:
            return None

    return versao("torch"), versao("torchaudio")


def rota_instalada_valida(rota: str, *, exige_instalada: bool = False) -> tuple[bool, str]:
    torch, audio = versoes_torch_instaladas()
    if torch is None and audio is None and not exige_instalada:
        return True, "OK venv vazia"
    esperado = "2.11.0+cu128" if rota == "cuda" else "2.11.0"
    if torch == audio == esperado:
        return True, f"OK torch/torchaudio da rota {rota}"
    return False, f"ERRO: venv incompatível com rota {rota}; use uma venv nova"


def processo_ativo(runner: Runner | None = None) -> bool:
    """Detecta app/worker pela linha de comando; consulta incerta bloqueia remoção."""
    runner = runner or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True))
    try:
        r = runner([
            "powershell", "-NoProfile", "-Command",
            "$ErrorActionPreference='Stop'; "
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" "
            "| ForEach-Object { $_.CommandLine }",
        ])
    except Exception:
        return True
    if r.returncode != 0:
        return True
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


def atalho_deste_checkout(caminho: Path, raiz: Path) -> bool:
    """Só reconhece o atalho criado para esta cópia do aplicativo."""
    try:
        script = (
            "$ErrorActionPreference='Stop'; "
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:TRANSKRIPTOR_ATALHO_INSPECAO); "
            "[Console]::WriteLine($s.TargetPath); [Console]::WriteLine($s.Arguments)"
        )
        ambiente = os.environ.copy()
        ambiente["TRANSKRIPTOR_ATALHO_INSPECAO"] = str(caminho)
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=10, env=ambiente,
        )
        if resultado.returncode:
            return False
        linhas = resultado.stdout.splitlines()
        if len(linhas) != 2:
            return False
        pythonw = (raiz / ".venv" / "Scripts" / "pythonw.exe").resolve()
        aplicativo = (raiz / "transkriptor.pyw").resolve()
        return (Path(linhas[0]).resolve() == pythonw
                and linhas[1].strip().strip('"') == str(aplicativo))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False


def desinstalar_normal(raiz: str | Path, *, apagar_dados: bool = False) -> None:
    """Remove apenas alvos conhecidos após conferir que o aplicativo parou."""
    if processo_ativo():
        raise RuntimeError("Transkriptor em execução ou consulta de processos indisponível")
    raiz = Path(raiz).resolve(strict=True)

    def dentro(alvo: Path, base: Path, nome: str) -> Path:
        resolvido = alvo.resolve()
        base = base.resolve()
        if resolvido.name != nome or not resolvido.is_relative_to(base) or resolvido == base:
            raise ValueError(f"alvo {nome} fora da raiz autorizada")
        return resolvido

    perfil = Path(os.environ["USERPROFILE"]).resolve()
    appdata = Path(os.environ["APPDATA"]).resolve()
    atalhos = (
        dentro(perfil / "Desktop" / "Transkriptor.lnk", perfil, "Transkriptor.lnk"),
        dentro(perfil / "OneDrive" / "Desktop" / "Transkriptor.lnk", perfil, "Transkriptor.lnk"),
        dentro(appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "transkriptor.lnk", appdata, "transkriptor.lnk"),
    )
    venv = dentro(raiz / ".venv", raiz, ".venv")
    dados = (
        dentro(raiz / "transcricoes", raiz, "transcricoes"),
        dentro(raiz / "audio", raiz, "audio"),
        dentro(raiz / "_modelo_voz", raiz, "_modelo_voz"),
        dentro(raiz / "config_user.json", raiz, "config_user.json"),
    ) if apagar_dados else ()
    for atalho in atalhos:
        if atalho.is_file() and atalho_deste_checkout(atalho, raiz):
            atalho.unlink()
    if venv.is_dir():
        shutil.rmtree(venv)
    for alvo in dados:
        if alvo.is_dir():
            shutil.rmtree(alvo)
        elif alvo.is_file():
            alvo.unlink()


def validar_raiz_gate(raiz: str | Path) -> Path:
    """Aceita somente descendente resolvido do diretório temporário do sistema."""
    alvo = Path(raiz).resolve()
    temporario = Path(tempfile.gettempdir()).resolve()
    if alvo == temporario or not alvo.is_relative_to(temporario):
        raise ValueError("gate exige raiz temporária dentro do diretório temporário do sistema")
    return alvo


def exigir_marcador_gate(raiz: str | Path) -> Path:
    """Vincula operações de aceite ao nonce efêmero criado pelo gate."""
    raiz = validar_raiz_gate(raiz)
    nonce = os.environ.get("TRANSKRIPTOR_GATE_NONCE", "")
    marcador = raiz / ".transkriptor-gate.json"
    if len(nonce) != 32 or not marcador.is_file():
        raise ValueError("marcador do gate ausente")
    try:
        dados = json.loads(marcador.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise ValueError("marcador do gate inválido") from erro
    if dados != {"root": str(raiz), "nonce": nonce}:
        raise ValueError("marcador do gate não corresponde à raiz")
    return raiz


def _alvo_gate(raiz: Path, alvo: Path, nome: str) -> Path:
    resolvido = alvo.resolve()
    if resolvido.name != nome or not resolvido.is_relative_to(raiz):
        raise ValueError(f"alvo {nome} fora da raiz temporária")
    return resolvido


def desinstalar_isolado(raiz: str | Path, shortcut_dir: str | Path) -> None:
    """Remove só a venv e atalhos sintéticos sob a raiz de aceite."""
    raiz = exigir_marcador_gate(raiz)
    atalhos = Path(shortcut_dir).resolve()
    if not atalhos.is_relative_to(raiz) or atalhos == raiz:
        raise ValueError("atalhos fora da raiz temporária")
    venv = _alvo_gate(raiz, raiz / ".venv", ".venv")
    for nome in ("Transkriptor.lnk", "transkriptor.lnk"):
        atalho = _alvo_gate(raiz, atalhos / nome, nome)
        if atalho.is_file():
            atalho.unlink()
    if venv.is_dir():
        shutil.rmtree(venv)


def instalar_isolado(raiz: str | Path, rota: str, shortcut_dir: str | Path) -> None:
    """Instala por lock em cópia temporária, com atalho somente simulado."""
    raiz = exigir_marcador_gate(raiz)
    if rota not in ("cpu", "cuda"):
        raise ValueError("rota inválida")
    if rota == "cuda" and not tem_gpu_nvidia():
        raise ValueError("CUDA sem GPU NVIDIA")
    atalhos = Path(shortcut_dir).resolve()
    if not atalhos.is_relative_to(raiz) or atalhos == raiz:
        raise ValueError("atalhos fora da raiz temporária")
    venv = _alvo_gate(raiz, raiz / ".venv", ".venv")
    if venv.exists():
        raise ValueError("venv já existente na raiz temporária")
    lock = raiz / "requirements" / f"requirements-{rota}.lock"
    if not lock.is_file():
        raise ValueError("lock da rota ausente")
    subprocess.run([sys.executable, "-m", "venv", str(venv)], cwd=raiz, check=True)
    python = venv / "Scripts" / "python.exe"
    subprocess.run([str(python), "-m", "pip", "install", "--require-hashes", "-r", str(lock)], cwd=raiz, check=True)
    subprocess.run([str(python), "-m", "pip", "check"], cwd=raiz, check=True)
    subprocess.run(
        [str(python), str(raiz / "scripts" / "instalar_helper.py"), "--check", "installed-route",
         "--rota", rota, "--require-installed"],
        cwd=raiz, check=True,
    )
    atalhos.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(raiz / "scripts" / "criar_atalho_desktop.ps1"),
         "-Pythonw", str(venv / "Scripts" / "pythonw.exe"),
         "-Aplicativo", str(raiz / "transkriptor.pyw"),
         "-Icone", str(raiz / "transkriptor.ico"),
         "-Destino", str(atalhos / "Transkriptor.lnk")],
        cwd=raiz, check=True,
    )


def _isolado_cli(argv: list[str]) -> int:
    acao = argv[0]
    parser = argparse.ArgumentParser(description="Instalação de aceite em raiz temporária")
    parser.add_argument("--non-interactive", action="store_true", required=True)
    parser.add_argument("--route", choices=("cpu", "cuda"))
    parser.add_argument("--skip-warmup", action="store_true")
    parser.add_argument("--preserve-data", action="store_true")
    parser.add_argument("--shortcut-dir", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    raiz = Path(__file__).resolve().parent.parent
    if acao == "--isolated-install":
        if not args.route or not args.skip_warmup:
            parser.error("instalação isolada exige rota e --skip-warmup")
        instalar_isolado(raiz, args.route, args.shortcut_dir)
    else:
        if not args.preserve_data:
            parser.error("desinstalação isolada exige --preserve-data")
        desinstalar_isolado(raiz, args.shortcut_dir)
    return 0


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if argv and argv[0] == "--uninstall-normal":
        if argv[1:] not in (["--preserve-data"], ["--delete-data"]):
            print("ERRO: escolha --preserve-data ou --delete-data")
            return 2
        desinstalar_normal(Path(__file__).resolve().parent.parent,
                           apagar_dados=argv[1] == "--delete-data")
        return 0
    if argv and argv[0] in ("--isolated-install", "--isolated-uninstall"):
        return _isolado_cli(argv)
    if argv == ["--version"]:
        import runpy
        from pathlib import Path

        config_path = Path(__file__).resolve().parent.parent / "config.py"
        print(runpy.run_path(str(config_path))["VERSAO"])
        return 0
    if argv == ["--route"]:
        print(_rota_detectada())
        return 0
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
    if oque == "installed-route":
        try:
            rota = argv[argv.index("--rota") + 1]
        except (ValueError, IndexError):
            rota = ""
        if rota not in ("cpu", "cuda"):
            print("ERRO: informe --rota cpu|cuda")
            return 2
        ok, msg = rota_instalada_valida(rota, exige_instalada="--require-installed" in argv)
        print(msg)
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
