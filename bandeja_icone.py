# -*- coding: utf-8 -*-
"""Ícone da bandeja (microfone) e cache por estado."""

from __future__ import annotations

from PIL import Image, ImageDraw

from config import ICONE_FILE
from estado_icone import COR_AGUARDANDO, cor_por_estado

_IMAGENS: dict = {}


def criar_imagem(cor_fundo=None, cor_mic=(255, 255, 255)):
    """Desenha um microfone simples para o ícone da bandeja."""
    if cor_fundo is None:
        cor_fundo = COR_AGUARDANDO
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill=cor_fundo)
    d.rounded_rectangle([24, 14, 40, 38], radius=8, fill=cor_mic)
    d.arc([16, 24, 48, 50], start=20, end=160, fill=cor_mic, width=4)
    d.rectangle([30, 46, 34, 54], fill=cor_mic)
    d.rectangle([24, 52, 40, 56], fill=cor_mic)
    return img


def imagem_por_estado(estado):
    """Retorna a imagem do ícone para o estado dado (com cache)."""
    if estado not in _IMAGENS:
        _IMAGENS[estado] = criar_imagem(cor_fundo=cor_por_estado(estado))
    return _IMAGENS[estado]


def criar_ico(caminho: str = ICONE_FILE):
    criar_imagem().save(caminho, format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])
    return caminho
