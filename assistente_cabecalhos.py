# -*- coding: utf-8 -*-
"""Cabeçalhos de privacidade e CSP da Central (SEC-14.A2).

Diretivas explícitas, sem 'unsafe-inline': nenhum estilo ou script inline e
nada carrega de fora de 127.0.0.1. Fontes, ícones e imagens são servidos pelo
próprio Flask; `data:` fica restrito a imagens.
"""
from __future__ import annotations

CSP_NORMATIVA = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)


def aplicar_cabecalhos(resposta):
    """Aplica os cabeçalhos de privacidade a uma resposta Flask e a devolve."""
    resposta.headers["Cache-Control"] = "no-store"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Content-Security-Policy"] = CSP_NORMATIVA
    return resposta
