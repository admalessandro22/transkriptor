# -*- coding: utf-8 -*-
"""Carrega front do assistente (template + CSS + JS) para asserts de UX."""
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def carregar_front_assistente() -> str:
    partes = [
        (_REPO / "templates" / "assistente.html").read_text(encoding="utf-8"),
        (_REPO / "static" / "assistente.css").read_text(encoding="utf-8"),
        (_REPO / "static" / "assistente.js").read_text(encoding="utf-8"),
    ]
    return "\n".join(partes)


HTML = carregar_front_assistente()
