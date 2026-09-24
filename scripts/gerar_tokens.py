# -*- coding: utf-8 -*-
"""Gera `static/css/tokens.css` e `design_tokens.py` a partir de `design/tokens.json`.

Fonte única dos tokens de design (SDD v1.9, T-14.A1). Uso:

    python scripts/gerar_tokens.py --check   # falha se os arquivos gerados divergem
    python scripts/gerar_tokens.py --write   # regrava os arquivos gerados

O verificador de contraste roda nos dois modos: nenhum par abaixo do mínimo
declarado em `contrast_pairs` pode ser escrito.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOKENS_PADRAO = REPO / "design" / "tokens.json"
CSS_PADRAO = REPO / "static" / "css" / "tokens.css"
PY_PADRAO = REPO / "design_tokens.py"
CABECALHO = "Gerado por scripts/gerar_tokens.py a partir de design/tokens.json. Não editar à mão."

_HEX = re.compile(r"^#([0-9a-fA-F]{6})$")
_RGBA = re.compile(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)$")


def carregar_tokens(caminho: Path = TOKENS_PADRAO) -> dict:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if dados.get("version") != 1:
        raise ValueError("tokens.json: versão não suportada")
    return dados


# ---- cor e contraste -------------------------------------------------------

def _parse_cor(valor: str) -> tuple[float, float, float, float]:
    valor = valor.strip()
    m = _HEX.match(valor)
    if m:
        h = m.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
    m = _RGBA.match(valor)
    if m:
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return r, g, b, a
    raise ValueError(f"cor não reconhecida: {valor!r}")


def _compor(frente: str, fundo: str) -> tuple[float, float, float]:
    fr, fg, fb, fa = _parse_cor(frente)
    br, bg, bb, _ = _parse_cor(fundo)
    return (
        fr * fa + br * (1 - fa),
        fg * fa + bg * (1 - fa),
        fb * fa + bb * (1 - fa),
    )


def _luminancia(rgb: tuple[float, float, float]) -> float:
    def canal(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(frente: str, fundo: str) -> float:
    """Razão de contraste WCAG; `frente` com alfa é composta sobre `fundo`."""
    l1 = _luminancia(_compor(frente, fundo))
    l2 = _luminancia(_compor(fundo, "#000000"))
    claro, escuro = max(l1, l2), min(l1, l2)
    return round((claro + 0.05) / (escuro + 0.05), 2)


def _resolver(tokens: dict, tema: str, nome: str) -> str:
    cores = tokens["color"]
    if nome in cores[tema]:
        return cores[tema][nome]
    if nome.startswith("state-") and nome[6:] in cores["state"]:
        return cores["state"][nome[6:]]
    raise KeyError(f"token de cor desconhecido em {tema}: {nome}")


def verificar_contraste(tokens: dict) -> list[str]:
    """Pares abaixo do mínimo, em ambos os temas. Lista vazia = aprovado."""
    falhas: list[str] = []
    for tema in ("dark", "light"):
        for frente, fundo, minimo in tokens["contrast_pairs"]:
            razao = contraste(_resolver(tokens, tema, frente), _resolver(tokens, tema, fundo))
            if razao < float(minimo):
                falhas.append(f"{tema}: {frente} sobre {fundo} = {razao} < {minimo}")
    return falhas


# ---- geração ---------------------------------------------------------------

def _bloco_cores(cores: dict, indent: str) -> list[str]:
    return [f"{indent}--tk-{nome}: {valor};" for nome, valor in cores.items()]


def gerar_css(tokens: dict) -> str:
    cor = tokens["color"]
    tipo = tokens["type"]
    linhas = [f"/* {CABECALHO} */", ":root {", "  color-scheme: dark light;"]
    linhas += _bloco_cores(cor["dark"], "  ")
    linhas += [f"  --tk-state-{k}: {v};" for k, v in cor["state"].items()]
    linhas += [
        f"  --tk-font-sans: {tipo['family-sans']};",
        f"  --tk-font-display: {tipo['family-display']};",
        f"  --tk-font-mono: {tipo['family-mono']};",
    ]
    for nome, (tamanho, entrelinha) in tipo["scale"].items():
        linhas.append(f"  --tk-type-{nome}-size: {tamanho}px;")
        linhas.append(f"  --tk-type-{nome}-line: {entrelinha}px;")
    for i, valor in enumerate(tokens["space"], start=1):
        linhas.append(f"  --tk-space-{i}: {valor}px;")
    for nome, valor in tokens["radius"].items():
        linhas.append(f"  --tk-radius-{nome}: {valor}px;")
    for nome, valor in tokens["elev"].items():
        linhas.append(f"  --tk-elev-{nome}: {valor};")
    mov = tokens["motion"]
    linhas += [
        f"  --tk-dur-fast: {mov['fast']}ms;",
        f"  --tk-dur-base: {mov['base']}ms;",
        f"  --tk-dur-slow: {mov['slow']}ms;",
        f"  --tk-ease: {mov['easing']};",
        "}",
        "@media (prefers-color-scheme: light) {",
        "  :root:not([data-theme=\"dark\"]) {",
    ]
    linhas += _bloco_cores(cor["light"], "    ")
    linhas += ["  }", "}", ":root[data-theme=\"light\"] {"]
    linhas += _bloco_cores(cor["light"], "  ")
    linhas += ["}", ""]
    return "\n".join(linhas)


def _rgb_tupla(valor: str) -> tuple[int, int, int]:
    r, g, b, _ = _parse_cor(valor)
    return int(r), int(g), int(b)


def gerar_python(tokens: dict) -> str:
    estados = tokens["color"]["state"]
    mapa = tokens["estado_icone"]
    linhas = [
        "# -*- coding: utf-8 -*-",
        f'"""{CABECALHO}"""',
        "",
        f"VERSAO_TOKENS = {tokens['version']}",
        "",
    ]
    for constante, chave in mapa.items():
        linhas.append(f"{constante} = {_rgb_tupla(estados[chave])!r}")
    linhas += ["", "ESTADOS = {"]
    for chave, valor in estados.items():
        linhas.append(f"    {chave!r}: {_rgb_tupla(valor)!r},")
    linhas += ["}", ""]
    return "\n".join(linhas)


# ---- linha de comando ------------------------------------------------------

def _ler(caminho: Path) -> str | None:
    try:
        return caminho.read_text(encoding="utf-8")
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--check", action="store_true")
    modo.add_argument("--write", action="store_true")
    parser.add_argument("--tokens", type=Path, default=TOKENS_PADRAO)
    parser.add_argument("--css", type=Path, default=CSS_PADRAO)
    parser.add_argument("--py", type=Path, default=PY_PADRAO)
    args = parser.parse_args(argv)

    tokens = carregar_tokens(args.tokens)
    falhas = verificar_contraste(tokens)
    if falhas:
        print("CONTRASTE REPROVADO", file=sys.stderr)
        for f in falhas:
            print(f"- {f}", file=sys.stderr)
        return 1

    saidas = {args.css: gerar_css(tokens), args.py: gerar_python(tokens)}
    if args.write:
        for caminho, conteudo in saidas.items():
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(conteudo, encoding="utf-8", newline="\n")
            print(f"gravado: {caminho}")
        return 0

    divergentes = [str(c) for c, conteudo in saidas.items() if _ler(c) != conteudo]
    if divergentes:
        print("TOKENS DESATUALIZADOS: " + ", ".join(divergentes), file=sys.stderr)
        return 1
    print("TOKENS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
