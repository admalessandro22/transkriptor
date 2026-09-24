# -*- coding: utf-8 -*-
"""Gera SBOM CycloneDX da árvore CPU instalada, com hashes do lock."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_LINHA_LOCK = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+) --hash=sha256:([0-9a-f]{64})$")


def _nome(valor: str) -> str:
    return re.sub(r"[-_.]+", "-", valor).lower()


def filtrar_sbom(sbom: dict, texto_lock: str) -> dict:
    """Retém a árvore de produção e confere versão/hash de cada componente."""
    if sbom.get("bomFormat") != "CycloneDX" or not isinstance(sbom.get("components"), list):
        raise ValueError("SBOM CycloneDX inválido")
    pinos = {}
    for linha in texto_lock.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith(("#", "-")):
            continue
        match = _LINHA_LOCK.fullmatch(linha)
        if match is None:
            raise ValueError("lock sem hash SHA-256")
        nome = _nome(match[1])
        if nome in pinos:
            raise ValueError("pacote duplicado no lock")
        pinos[nome] = (match[2], match[3])
    if not pinos:
        raise ValueError("lock vazio")

    componentes = []
    vistos = set()
    refs = set()
    for item in sbom["components"]:
        nome = _nome(item.get("name", ""))
        if nome not in pinos:
            continue
        if nome in vistos or item.get("version") != pinos[nome][0]:
            raise ValueError("versão duplicada ou divergente no SBOM")
        visto = dict(item)
        visto["hashes"] = [{"alg": "SHA-256", "content": pinos[nome][1]}]
        componentes.append(visto)
        vistos.add(nome)
        ref = item.get("bom-ref") or item.get("bomRef")
        if ref:
            refs.add(ref)
    if vistos != set(pinos):
        raise ValueError("SBOM não cobre todo o lock CPU")
    componentes.sort(key=lambda item: _nome(item["name"]))
    saida = dict(sbom)
    saida["components"] = componentes
    if "dependencies" in saida:
        saida["dependencies"] = [
            {**item, "dependsOn": [ref for ref in item.get("dependsOn", []) if ref in refs]}
            for item in saida["dependencies"]
            if item.get("ref") in refs
        ]
    return saida


def gerar_sbom(python: Path, lock: Path, destino: Path) -> None:
    """Usa a CLI CycloneDX na venv resolvida e remove apenas ferramentas dev."""
    with tempfile.TemporaryDirectory(prefix="transkriptor-sbom-") as pasta:
        bruto = Path(pasta) / "sbom.json"
        subprocess.run(
            [str(python), "-m", "cyclonedx_py", "environment", "--output-reproducible",
             "--output-format", "JSON", "--output-file", str(bruto)],
            check=True, capture_output=True, text=True,
        )
        dados = json.loads(bruto.read_text(encoding="utf-8"))
    filtrado = filtrar_sbom(dados, lock.read_text(encoding="utf-8"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(filtrado, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--lock", type=Path, default=Path("requirements/requirements-cpu.lock"))
    parser.add_argument("--output", type=Path, default=Path("docs/sbom.json"))
    args = parser.parse_args()
    gerar_sbom(args.python, args.lock, args.output)


if __name__ == "__main__":
    main()
