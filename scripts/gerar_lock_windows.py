# -*- coding: utf-8 -*-
"""Converte pinos pip-tools + relatório pip em lock Windows com hashes.

pip-tools enumera wheels de todas as plataformas com --generate-hashes. O
relatório do pip seleciona os artefatos Windows/Python 3.12 efetivos.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CUDA_INDEX = "https://download.pytorch.org/whl/cu128"
_PINO = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==([^\s;]+)$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _nome(valor: str) -> str:
    return re.sub(r"[-_.]+", "-", valor).lower()


def gerar_lock(
    pins: str | Path, relatorio: str | Path, destino: str | Path, *, cuda: bool = False
) -> None:
    """Exige correspondência exata de todos os pinos e SHA-256 do artefato."""
    pins = Path(pins)
    relatorio = Path(relatorio)
    destino = Path(destino)
    esperados: dict[str, str] = {}
    for linha in pins.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith(("#", "-")):
            continue
        match = _PINO.fullmatch(linha)
        if match is None:
            raise ValueError("pino inválido")
        nome, versao = _nome(match[1]), match[2]
        if nome in esperados:
            raise ValueError("pino duplicado")
        esperados[nome] = versao

    dados = json.loads(relatorio.read_text(encoding="utf-8"))
    if dados.get("version") != "1" or not isinstance(dados.get("install"), list):
        raise ValueError("relatório pip inválido")
    encontrados: dict[str, tuple[str, str]] = {}
    for item in dados["install"]:
        try:
            nome = _nome(item["metadata"]["name"])
            versao = item["metadata"]["version"]
            hash_sha256 = item["download_info"]["archive_info"]["hashes"]["sha256"]
        except (KeyError, TypeError) as exc:
            raise ValueError("relatório sem hash ou pacote") from exc
        if not isinstance(hash_sha256, str) or not _SHA256.fullmatch(hash_sha256):
            raise ValueError("hash SHA-256 inválido")
        if nome in encontrados:
            raise ValueError("pacote duplicado no relatório")
        encontrados[nome] = (versao, hash_sha256)
    if set(encontrados) != set(esperados):
        raise ValueError("árvore do relatório difere dos pinos")
    if any(encontrados[nome][0] != versao for nome, versao in esperados.items()):
        raise ValueError("versão do relatório difere dos pinos")

    linhas = [
        "# Lock Windows/Python 3.12: pip-compile + pip install --dry-run --report.",
        "# Regeneração: docs/DEPENDENCIAS.md. Cada hash identifica o artefato selecionado.",
    ]
    if cuda:
        linhas.append(f"--extra-index-url {CUDA_INDEX}")
    for nome in sorted(esperados):
        versao, hash_sha256 = encontrados[nome]
        linhas.append(f"{nome}=={versao} --hash=sha256:{hash_sha256}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def gerar_cuda_de_cpu(cpu: str | Path, destino: str | Path, torch_sha: str, torchaudio_sha: str) -> None:
    """Deriva a árvore CUDA do lock CPU com hashes dos wheels oficiais Win cp312."""
    if not all(_SHA256.fullmatch(sha) for sha in (torch_sha, torchaudio_sha)):
        raise ValueError("hash SHA-256 inválido")
    linhas = Path(cpu).read_text(encoding="utf-8").splitlines()
    saida = [
        "# CUDA 12.8 Windows/Python 3.12; hashes dos wheels oficiais PyTorch cp312 win_amd64.",
        "# Regeneração e proveniência: docs/DEPENDENCIAS.md.",
        f"--extra-index-url {CUDA_INDEX}",
    ]
    trocados = set()
    for linha in linhas:
        if not linha or linha.startswith(("#", "--")):
            continue
        nome, _, restante = linha.partition("==")
        if not _PINO.fullmatch(f"{nome}=={restante.split(' --hash=')[0]}") or " --hash=sha256:" not in linha:
            raise ValueError("lock CPU inválido")
        if nome in ("torch", "torchaudio"):
            if nome in trocados or not linha.startswith(f"{nome}==2.11.0 --hash=sha256:"):
                raise ValueError("pino PyTorch CPU inválido")
            hash_novo = torch_sha if nome == "torch" else torchaudio_sha
            linha = f"{nome}==2.11.0+cu128 --hash=sha256:{hash_novo}"
            trocados.add(nome)
        saida.append(linha)
    if trocados != {"torch", "torchaudio"}:
        raise ValueError("lock CPU sem torch e torchaudio")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(saida) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pins", type=Path)
    parser.add_argument("relatorio", type=Path)
    parser.add_argument("destino", type=Path)
    parser.add_argument("--cuda", action="store_true")
    args = parser.parse_args()
    gerar_lock(args.pins, args.relatorio, args.destino, cuda=args.cuda)


if __name__ == "__main__":
    main()
