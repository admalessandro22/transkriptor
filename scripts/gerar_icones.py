# -*- coding: utf-8 -*-
"""Gera os ícones do Transkriptor a partir da geometria de `bandeja_icone` (UX-14.E1).

    python scripts/gerar_icones.py --write   # transkriptor.ico, static/favicon.ico,
                                             # static/icones/bandeja/<estado>.png, extension/meet/icons/*.png
    python scripts/gerar_icones.py --check   # compara os PNGs por estado com o desenho atual

A fonte vetorial de referência é `design/icone/transkriptor.svg`; o desenho PIL
reproduz a mesma geometria porque a stack não tem rasterizador SVG.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from bandeja_icone import desenhar_icone  # noqa: E402
from design_tokens import ESTADOS  # noqa: E402

ESTADOS_ICONE = ("aguardando", "transcrevendo", "diarizando", "processando", "erro", "pausado")
TAMANHOS_ICO = (16, 20, 24, 32, 48, 256)
TAMANHOS_PNG = (16, 32, 64)
TAMANHOS_EXTENSAO = (16, 32, 48, 128)


def png_bytes(tamanho: int, estado: str | None) -> bytes:
    buf = io.BytesIO()
    desenhar_icone(tamanho, estado).save(buf, format="PNG")
    return buf.getvalue()


def gerar_ico(destino: Path, tamanhos=TAMANHOS_ICO) -> Path:
    quadros = [desenhar_icone(t, None) for t in tamanhos]
    destino.parent.mkdir(parents=True, exist_ok=True)
    quadros[-1].save(destino, format="ICO", sizes=[(t, t) for t in tamanhos], append_images=quadros[:-1])
    return destino


def gerar_estados(pasta: Path, tamanhos=TAMANHOS_PNG) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    saidas = []
    for estado in ESTADOS_ICONE:
        for t in tamanhos:
            nome = f"{estado}.png" if t == 64 else f"{estado}-{t}.png"
            caminho = pasta / nome
            caminho.write_bytes(png_bytes(t, estado))
            saidas.append(caminho)
    return saidas


def gerar_extensao(pasta: Path, tamanhos=TAMANHOS_EXTENSAO) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    saidas = []
    for t in tamanhos:
        caminho = pasta / f"icone-{t}.png"
        caminho.write_bytes(png_bytes(t, None))
        saidas.append(caminho)
    return saidas


def verificar(pasta: Path) -> list[str]:
    """PNGs por estado divergentes do desenho atual (lista vazia = ok)."""
    divergentes = []
    for estado in ESTADOS_ICONE:
        caminho = pasta / f"{estado}.png"
        if not caminho.is_file() or caminho.read_bytes() != png_bytes(64, estado):
            divergentes.append(str(caminho))
    return divergentes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--check", action="store_true")
    modo.add_argument("--write", action="store_true")
    parser.add_argument("--raiz", type=Path, default=REPO)
    args = parser.parse_args(argv)
    raiz = args.raiz
    pasta_png = raiz / "static" / "icones" / "bandeja"
    if args.check:
        divergentes = verificar(pasta_png)
        if divergentes:
            print("ICONES DESATUALIZADOS: " + ", ".join(divergentes), file=sys.stderr)
            return 1
        print("ICONES OK")
        return 0
    gerar_ico(raiz / "transkriptor.ico")
    gerar_ico(raiz / "static" / "favicon.ico", tamanhos=(16, 32, 48))
    gerar_estados(pasta_png)
    gerar_extensao(raiz / "extension" / "meet" / "icons")
    print(f"gerados: transkriptor.ico, static/favicon.ico, {len(ESTADOS_ICONE) * len(TAMANHOS_PNG)} PNGs de estado, {len(TAMANHOS_EXTENSAO)} ícones da extensão; estados dos tokens: {sorted(ESTADOS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
