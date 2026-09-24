# -*- coding: utf-8 -*-
"""Gate CPU/CUDA em cópia temporária, sem alterar a instalação em uso."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from scripts.instalar_helper import alvos_desinstalacao, validar_raiz_gate
except ModuleNotFoundError:  # execução direta: scripts/ no sys.path
    from instalar_helper import alvos_desinstalacao, validar_raiz_gate

REPO = Path(__file__).resolve().parent.parent

_PROVA_INSTANCIA = r'''
import json, socket, sys, time
from pathlib import Path
from transkriptor_lock import adquirir_lock, liberar_lock
lock, marcador = Path(sys.argv[1]), Path(sys.argv[2])
ok = adquirir_lock(lock, usar_mutex_nomeado=False)
porta = 0
servidor = None
if ok:
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(1)
    porta = servidor.getsockname()[1]
marcador.write_text(json.dumps({"acquired": ok, "port": porta}), encoding="utf-8")
if ok:
    time.sleep(30)
    servidor.close()
    liberar_lock()
'''


def arquivos_versionados(repo: Path = REPO) -> list[Path]:
    """Retorna somente caminhos rastreados; nunca inclui arquivos locais ignorados."""
    raw = subprocess.run(["git", "ls-files", "-z"], cwd=repo, check=True, capture_output=True).stdout
    arquivos = [Path(nome.decode("utf-8")) for nome in raw.split(b"\0") if nome]
    for relativo in arquivos:
        if relativo.is_absolute() or ".." in relativo.parts:
            raise ValueError("Git retornou path fora do repositório")
    return arquivos


def copiar_versionados(repo: Path, destino: Path) -> int:
    repo = repo.resolve()
    destino = validar_raiz_gate(destino)
    copiados = 0
    for relativo in arquivos_versionados(repo):
        origem = (repo / relativo).resolve()
        if not origem.is_relative_to(repo) or not origem.is_file():
            raise ValueError("arquivo versionado fora do repositório")
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo)
        copiados += 1
    return copiados


def _esperar_marcador(marcador: Path, processo: subprocess.Popen, timeout: float = 15) -> dict:
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if marcador.is_file():
            return json.loads(marcador.read_text(encoding="utf-8"))
        if processo.poll() is not None:
            raise RuntimeError("filho terminou antes do marcador de instância")
        time.sleep(0.1)
    raise TimeoutError("filho não iniciou no prazo")


def provar_instancia(raiz: Path, python: Path, *, codigo_root: Path = REPO) -> dict:
    """Prova lock exclusivo/porta local com dois PIDs filhos conhecidos."""
    raiz = Path(raiz).resolve()
    raiz.mkdir(parents=True, exist_ok=True)
    lock = raiz / ".gate-instancia.lock"
    primeiro = raiz / ".gate-primeiro.json"
    segundo = raiz / ".gate-segundo.json"
    comando = [str(python), "-c", _PROVA_INSTANCIA, str(lock)]
    filho = subprocess.Popen(
        [*comando, str(primeiro)], cwd=codigo_root, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        um = _esperar_marcador(primeiro, filho)
        if not um["acquired"] or um["port"] <= 0:
            raise AssertionError("primeiro filho não adquiriu lock/porta")
        with socket.create_connection(("127.0.0.1", um["port"]), timeout=2):
            pass
        outro = subprocess.Popen(
            [*comando, str(segundo)], cwd=codigo_root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            outro.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            outro.kill()
            outro.communicate()
            raise
        if outro.returncode:
            raise RuntimeError("segundo filho falhou")
        dois = json.loads(segundo.read_text(encoding="utf-8"))
        if dois["acquired"] or dois["port"]:
            raise AssertionError("segunda instância adquiriu lock/porta")
        return {
            "instancias_primeiro_start": 1,
            "instancias_segundo_start": 1,
            "pid_filho": filho.pid,
            "pid_segundo_filho": outro.pid,
            "porta": um["port"],
            "segundo_exit_code": outro.returncode,
        }
    finally:
        if filho.poll() is None:
            filho.terminate()
            try:
                filho.wait(timeout=5)
            except subprocess.TimeoutExpired:
                filho.kill()
                filho.wait(timeout=5)


def _executar_batch(caminho: Path, argumentos: list[str], raiz: Path, nonce: str) -> None:
    ambiente = os.environ.copy()
    ambiente["PIP_NO_CACHE_DIR"] = "1"
    ambiente["TRANSKRIPTOR_GATE_NONCE"] = nonce
    ambiente["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    resultado = subprocess.run(
        [str(caminho), *argumentos], cwd=raiz, env=ambiente,
        capture_output=True, text=True,
    )
    if resultado.returncode:
        raise RuntimeError(f"{caminho.name} falhou (exit {resultado.returncode}): "
                           f"{resultado.stdout[-700:]} {resultado.stderr[-700:]}")


def executar_gate(rota: str = "cpu") -> dict:
    if rota not in ("cpu", "cuda"):
        raise ValueError("rota inválida")
    pasta = Path(tempfile.mkdtemp(prefix="transkriptor-gate-"))
    validar_raiz_gate(pasta)
    try:
        raiz = validar_raiz_gate(pasta / "Pasta Com Acento çã")
        raiz.mkdir()
        nonce = secrets.token_hex(16)
        (raiz / ".transkriptor-gate.json").write_text(
            json.dumps({"root": str(raiz), "nonce": nonce}), encoding="utf-8")
        atalhos_reais = [Path(p) for p in alvos_desinstalacao()["atalhos"]]
        def estado_atalhos() -> dict[str, str | None]:
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
                    for p in atalhos_reais}
        estado_inicial = estado_atalhos()
        quantidade = copiar_versionados(REPO, raiz)
        atalhos = raiz / "Desktop falso"
        dados = {
            raiz / "transcricoes" / "canario.bin": b"transcricao-sintetica",
            raiz / "_modelo_voz" / "canario.bin": b"perfil-sintetico",
            raiz / "config_user.json": b"{}",
        }
        for caminho, conteudo in dados.items():
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_bytes(conteudo)
        hashes = {str(c.relative_to(raiz)): hashlib.sha256(c.read_bytes()).hexdigest() for c in dados}
        _executar_batch(
            raiz / "instalar.bat",
            ["--non-interactive", "--route", rota, "--skip-warmup", "--shortcut-dir", str(atalhos)],
            raiz, nonce,
        )
        python = raiz / ".venv" / "Scripts" / "python.exe"
        atalho = atalhos / "Transkriptor.lnk"
        if not python.is_file() or not atalho.is_file():
            raise AssertionError("instalação não criou venv/atalho isolados")
        instancias = provar_instancia(raiz, python, codigo_root=raiz)
        _executar_batch(
            raiz / "desinstalar.bat",
            ["--non-interactive", "--preserve-data", "--shortcut-dir", str(atalhos)],
            raiz, nonce,
        )
        preservados = all(
            c.is_file() and hashlib.sha256(c.read_bytes()).hexdigest() == hashes[str(c.relative_to(raiz))]
            for c in dados
        )
        removida = not (raiz / ".venv").exists() and not atalho.exists()
        if not preservados or not removida:
            raise AssertionError("desinstalação não preservou dados ou manteve alvos")
        alvos_reais_intocados = estado_atalhos() == estado_inicial
        if not alvos_reais_intocados:
            raise AssertionError("um atalho real mudou durante o gate")
        return {
            "rota": rota,
            "raiz_temporaria": str(raiz),
            "arquivos_versionados": quantidade,
            **instancias,
            "hashes_dados_sinteticos": hashes,
            "dados_preservados": preservados,
            "venv_removida": removida,
            "atalhos_reais_intocados": alvos_reais_intocados,
            "escopo_prova_instancia": "harness_lock_arquivo_e_porta_local_sem_bandeja",
        }
    finally:
        # O único delete recursivo é a pasta mkdtemp validada nesta execução.
        validar_raiz_gate(pasta)
        shutil.rmtree(pasta)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    print(json.dumps(executar_gate(args.route), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
