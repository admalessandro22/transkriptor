# -*- coding: utf-8 -*-
"""F11.C — Assistente a11y e responsivo (T-11.C1).

Reduzido na v1.9 (T-14.F1) às presenças de CSS que não têm equivalente
comportamental: esquema de cores, anel de foco, `forced-colors` e
`prefers-reduced-motion`. O resto virou E2E: drawer/aria e Tab em
`tests/e2e/shell.spec.js` e `accessibility.spec.js`; setas/Ctrl+K em
`reunioes.spec.js`; Escape/abort em `chat-cancel.spec.js`; larguras em
`larguras.spec.js`; axe em `axe.spec.js`.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from tests.front_assistente import CSS  # v1.9: base + módulos


def test_color_scheme_dark():
    tokens = (REPO / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    assert "color-scheme: dark light" in tokens
    assert "@import url(\"css/tokens.css\")" in CSS


def test_focus_visible_accent():
    assert ":focus-visible { outline: 2px solid var(--tk-accent)" in CSS  # base.css


def test_forced_colors_presente():
    assert "@media (forced-colors: active)" in CSS
    assert "CanvasText" in CSS or "forced-color-adjust" in CSS


def test_reduced_motion_presente():
    assert "@media (prefers-reduced-motion: reduce)" in CSS
