#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Relação versão do app × versão da extensão (T-13.G2).

A extensão tem versão independente, mas derivada da release: acompanha
major.minor do app com patch próprio. `--check` valida sem escrever.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def versao_extensao_para(versao_app: str) -> str:
    m = re.fullmatch(r"\s*(\d+)\.(\d+)\.\d+.*", str(versao_app))
    if not m:
        raise ValueError(f"versão do app inválida: {versao_app}")
    return f"{m.group(1)}.{m.group(2)}.0"


def manifest_atualizado(raiz: Path, versao_app: str, *, aplicar: bool = False) -> str:
    import re as _re

    alvo = versao_extensao_para(versao_app)
    caminho = Path(raiz) / "extension" / "meet" / "manifest.json"
    texto = caminho.read_text(encoding="utf-8")
    dados = json.loads(texto)
    if aplicar and dados.get("version") != alvo:
        novo, n = _re.subn(r'"version"\s*:\s*"[^"]*"', f'"version": "{alvo}"', texto, count=1)
        caminho.write_text(novo if n else json.dumps({**dados, "version": alvo}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return alvo


def main(argv=None) -> int:
    argv = list(argv or sys.argv[1:])
    raiz = Path(__file__).resolve().parent.parent
    if argv[:1] == ["--check"]:
        import config

        alvo = versao_extensao_para(config.VERSAO)
        dados = json.loads((raiz / "extension" / "meet" / "manifest.json").read_text(encoding="utf-8"))
        if dados.get("version") != alvo:
            print(f"ERRO: manifest {dados.get('version')} != {alvo} (rode --aplicar)")
            return 1
        print(f"OK extensão {alvo} para release {config.VERSAO}")
        return 0
    if argv[:1] == ["--aplicar"]:
        import config

        alvo = manifest_atualizado(raiz, config.VERSAO, aplicar=True)
        print(f"OK manifest em {alvo}")
        return 0
    print("Uso: sincronizar_versao_extensao.py --check|--aplicar")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
