# -*- coding: utf-8 -*-
"""HTML/CSS/JS do assistente concatenados para os testes de contrato (v1.9: shell + módulos)."""
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def _ler(*partes):
    return (_REPO.joinpath(*partes)).read_text(encoding="utf-8")


def _todos(pasta, sufixo):
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((_REPO / pasta).glob("*" + sufixo)))


HTML_TEMPLATE = _ler("templates", "base.html") + "\n" + _ler("templates", "assistente.html")
CSS = _todos("static/css", ".css") + "\n" + _ler("static", "assistente.css")
JS = _todos("static/js", ".js") + "\n" + _ler("static", "assistente.js")
HTML = "\n".join([HTML_TEMPLATE, CSS, JS])
