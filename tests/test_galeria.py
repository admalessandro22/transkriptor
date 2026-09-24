# -*- coding: utf-8 -*-
"""UX-14.A3 — galeria de componentes e fundação visual (T-14.A3)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CSS_DIR = REPO / "static" / "css"


@pytest.fixture()
def cliente(monkeypatch):
    import assistente

    assistente.app.config["TESTING"] = True
    monkeypatch.delenv("TRANSKRIPTOR_GALERIA", raising=False)
    return assistente.app.test_client()


def test_galeria_desativada_por_padrao(cliente):
    assert cliente.get("/galeria").status_code == 404


def test_galeria_ativa_com_variavel(cliente, monkeypatch):
    monkeypatch.setenv("TRANSKRIPTOR_GALERIA", "1")
    resposta = cliente.get("/galeria")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    assert 'data-componente="tk-btn"' in html
    assert "style-src 'self'" in resposta.headers["Content-Security-Policy"]
    assert not re.search(r"\sstyle\s*=", html)


def test_componentes_cobrem_o_design_system():
    componentes = (CSS_DIR / "components.css").read_text(encoding="utf-8")
    for classe in ("tk-btn", "tk-field", "tk-listbox", "tk-badge-state", "tk-badge-protect", "tk-toast", "tk-dialog",
                   "tk-panel", "tk-skeleton", "tk-empty", "tk-row", "tk-progress", "tk-chip", "tk-statusbar"):
        assert f".{classe}" in componentes, classe
    for estado in ("aguardando", "gravando", "processando", "separando_vozes", "pausado", "erro"):
        assert f'[data-estado="{estado}"]' in componentes


def test_fundacao_sem_efeitos_proibidos():
    css = "\n".join(p.read_text(encoding="utf-8") for p in REPO.glob("static/**/*.css"))
    for proibido in ("backdrop-filter", "radial-gradient", "Georgia", "bounce", "elastic"):
        assert proibido not in css, proibido
    assert not re.search(r"(?<!sans-)serif", css), "fonte serifada fora de sans-serif"
    base = (CSS_DIR / "base.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in base and "forced-colors" in base
    assert ":focus-visible" in base


def test_galeria_sem_emoji_nem_glifo_como_icone():
    html = (REPO / "templates" / "galeria.html").read_text(encoding="utf-8")
    assert not re.search(r"[☀-➿\U0001F300-\U0001FAFF]", html)
    assert "●" not in html and "☰" not in html
    assert html.count("icones.svg") >= 20
