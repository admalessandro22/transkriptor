# -*- coding: utf-8 -*-
"""SEC-14.A2 — CSP explícita sem estilo inline (T-14.A2).

Cobre o cabeçalho enviado por `assistente.py` e a ausência de estilo inline
no HTML/JS servidos. O teste E2E `tests/e2e/csp.spec.js` carrega a página sob
a mesma CSP e reprova violações no console do navegador.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HTML = (REPO / "templates" / "assistente.html").read_text(encoding="utf-8")
JS = (REPO / "static" / "assistente.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cliente():
    import assistente

    assistente.app.config["TESTING"] = True
    return assistente.app.test_client()


def _csp(cliente) -> dict[str, str]:
    resposta = cliente.get("/")
    bruto = resposta.headers.get("Content-Security-Policy", "")
    diretivas = {}
    for parte in bruto.split(";"):
        parte = parte.strip()
        if parte:
            nome, _, valor = parte.partition(" ")
            diretivas[nome] = valor.strip()
    return diretivas


def test_csp_sem_unsafe_inline(cliente):
    diretivas = _csp(cliente)
    assert "unsafe-inline" not in " ".join(diretivas.values())
    assert diretivas.get("style-src") == "'self'"
    assert diretivas.get("script-src") == "'self'"
    assert diretivas.get("default-src") == "'none'"


def test_csp_img_permite_data_e_self(cliente):
    diretivas = _csp(cliente)
    assert diretivas.get("img-src") == "'self' data:"
    assert diretivas.get("connect-src") == "'self'"
    assert diretivas.get("base-uri") == "'none'"


def test_csp_mantem_frame_ancestors(cliente):
    assert _csp(cliente).get("frame-ancestors") == "'none'"


def test_html_sem_atributo_style():
    assert not re.search(r"\sstyle\s*=", HTML), "atributo style= no template"
    assert "<style" not in HTML
    assert not re.search(r"<script(?![^>]*\ssrc=)[^>]*>", HTML), "script inline no template"


def test_html_sem_glifo_de_compatibilidade_e_com_favicon():
    assert "☰" not in HTML and "&#9776;" not in HTML
    base = (REPO / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'rel="icon"' in base  # v1.9 (T-14.B1): o shell base.html carrega o favicon
    assert (REPO / "static" / "favicon.ico").is_file()


def test_js_nao_define_layout_por_style():
    proibidos = re.findall(r"\.style\.(display|flexDirection|gap|minWidth|flex|borderColor|opacity|transform|transition)\b", JS)
    assert not proibidos, f"layout via element.style no JS: {sorted(set(proibidos))}"
    assert "setAttribute('style'" not in JS and 'setAttribute("style"' not in JS


def test_sprite_de_icones_existe_com_minimo():
    sprite = (REPO / "static" / "icones.svg").read_text(encoding="utf-8")
    for nome in ("i-search", "i-x", "i-stop", "i-send", "i-menu"):
        assert f'id="{nome}"' in sprite
