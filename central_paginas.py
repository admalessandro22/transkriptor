# -*- coding: utf-8 -*-
"""Páginas da Central (UX-14.B1): shell, galeria e páginas ainda não entregues."""
from __future__ import annotations

import os

from flask import Blueprint, jsonify, render_template

from config import BASE_DIR

bp = Blueprint("central_paginas", __name__)


def _template_existe(pagina: str) -> bool:
    return os.path.isfile(os.path.join(BASE_DIR, "templates", f"{pagina}.html"))

PAGINAS_CENTRAL = ("inicio", "reunioes", "participantes", "configuracoes", "diagnostico")


@bp.route("/<pagina>")
def pagina_central(pagina: str):
    """UX-14.B1: páginas da Central; as ainda não entregues respondem 404 com o shell."""
    if pagina in PAGINAS_CENTRAL and _template_existe(pagina):
        return render_template(f"{pagina}.html")
    if pagina in PAGINAS_CENTRAL:
        return render_template("indisponivel.html"), 404
    return jsonify({"erro": "Página não encontrada"}), 404


@bp.route("/galeria")
def galeria():
    """UX-14.A3: galeria de componentes, só para revisão visual local."""
    if os.environ.get("TRANSKRIPTOR_GALERIA") != "1":
        return jsonify({"erro": "Galeria desativada"}), 404
    return render_template("galeria.html")
