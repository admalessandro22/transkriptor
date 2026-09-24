# -*- coding: utf-8 -*-
"""NFR-14.F2 — orçamento do front e zero rede (T-14.F2).

Soma bytes de `static/css`, `static/js`, do sprite de ícones e dos ICOs; falha
ao exceder. A parte comportamental (nenhuma requisição fora de 127.0.0.1 em
todas as páginas) está em `tests/e2e/csp.spec.js`.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KB = 1024
LIMITE_CSS = 80 * KB
LIMITE_JS = 150 * KB
LIMITE_SPRITE = 40 * KB
LIMITE_ICO = 64 * KB  # transkriptor.ico (6 tamanhos) + favicon


def _soma(pasta: Path, sufixo: str) -> tuple[int, list[str]]:
    arquivos = sorted(p for p in pasta.glob("*" + sufixo) if p.is_file())
    return sum(p.stat().st_size for p in arquivos), [p.name for p in arquivos]


def test_css_ate_80kb():
    total, nomes = _soma(REPO / "static" / "css", ".css")
    assert nomes, "static/css vazio"
    assert total <= LIMITE_CSS, f"CSS = {total} B > {LIMITE_CSS} B ({nomes})"


def test_js_ate_150kb():
    total, nomes = _soma(REPO / "static" / "js", ".js")
    assert nomes, "static/js vazio"
    assert total <= LIMITE_JS, f"JS = {total} B > {LIMITE_JS} B ({nomes})"


def test_sprite_ate_40kb():
    sprite = REPO / "static" / "icones.svg"
    assert sprite.is_file()
    assert sprite.stat().st_size <= LIMITE_SPRITE


def test_icos_ate_64kb():
    total = sum((REPO / nome).stat().st_size for nome in ("transkriptor.ico", "static/favicon.ico"))
    assert total <= LIMITE_ICO


def test_entradas_legadas_removidas():
    """T-14.F2: static/assistente.css e static/assistente.js não existem mais; nada as referencia."""
    assert not (REPO / "static" / "assistente.css").exists()
    assert not (REPO / "static" / "assistente.js").exists()
    for template in (REPO / "templates").glob("*.html"):
        texto = template.read_text(encoding="utf-8")
        assert "filename='assistente.css'" not in texto and "filename='assistente.js'" not in texto, template.name


def test_nenhuma_url_externa_no_front():
    """Zero rede: CSS, JS e templates não apontam para http(s) fora do loopback."""
    padrao = re.compile(r"https?://(?!127\.0\.0\.1|localhost)[^\s\"')]+")
    suspeitas = []
    for pasta, sufixo in (("static/css", ".css"), ("static/js", ".js"), ("templates", ".html")):
        for arquivo in sorted((REPO / pasta).glob("*" + sufixo)):
            for linha in arquivo.read_text(encoding="utf-8").splitlines():
                if linha.strip().startswith(("//", "*", "/*", "<!--", "#")):
                    continue  # comentários podem citar especificações
                for m in padrao.finditer(linha):
                    if "www.w3.org/2000/svg" in m.group(0):
                        continue  # namespace SVG não é requisição
                    suspeitas.append(f"{arquivo.name}: {m.group(0)}")
    assert suspeitas == []
