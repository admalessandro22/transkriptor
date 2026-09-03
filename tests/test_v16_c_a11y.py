# -*- coding: utf-8 -*-
"""F11.C — Assistente a11y e responsivo (T-11.C1)."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HTML = (REPO / "templates" / "assistente.html").read_text(encoding="utf-8")
CSS = (REPO / "static" / "assistente.css").read_text(encoding="utf-8")
JS = (REPO / "static" / "assistente.js").read_text(encoding="utf-8")
FRONT = HTML + "\n" + CSS + "\n" + JS


def test_color_scheme_dark():
    assert "color-scheme" in CSS
    assert "dark" in CSS


def test_focus_visible_gold():
    assert "focus-visible" in CSS
    assert "gold-bright" in CSS or "#e0c483" in CSS


def test_aria_labels_drawer():
    assert 'aria-label="Abrir menu' in HTML
    assert 'aria-expanded' in JS
    assert 'aria-controls="sidebar"' in HTML
    assert 'role="log"' in HTML
    assert 'aria-live="polite"' in HTML


def test_drawer_860_e_375():
    assert "860px" in CSS
    assert "375px" in CSS
    assert "drawer-open" in CSS
    assert "drawer-overlay" in HTML
    assert "translateX(-100%)" in CSS
    assert "cubic-bezier(0.32,0.72,0,1)" in CSS


def test_keyboard_nav_cards():
    assert "ArrowDown" in JS
    assert "ArrowUp" in JS
    assert "TEXTAREA" in JS
    assert "idx === -1" in JS
    assert "buscaInput" in JS
    assert "Ctrl+K" in JS or "ctrlKey" in JS


def test_esc_fecha_drawer_e_abort():
    assert "Escape" in JS
    assert "abortController.abort()" in JS
    assert "abrirDrawer(false)" in JS


def test_forced_colors_e_scrollbar():
    assert "forced-colors" in CSS
    assert "scrollbar-gutter" in CSS or "CanvasText" in CSS
