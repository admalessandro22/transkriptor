# -*- coding: utf-8 -*-
"""Ícone da bandeja: quadrado arredondado + microfone + glifo de estado (UX-14.E1).

A geometria é a mesma de `design/icone/transkriptor.svg` (fonte vetorial
versionada); como a stack não tem rasterizador SVG, o desenho é reproduzido
aqui com PIL, em qualquer tamanho, e `scripts/gerar_icones.py` usa esta
função para gerar ICO, PNGs por estado, favicon e ícones da extensão.
Estados diferem por FORMA (ponto, engrenagem, ondas, pausa, exclamação),
não só por cor, e as cores vêm dos tokens (`design_tokens`).
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw

from config import BASE_DIR, ICONE_FILE
from estado_icone import COR_AGUARDANDO, cor_por_estado

PASTA_PNG = os.path.join(BASE_DIR, "static", "icones", "bandeja")
BRANCO = (255, 255, 255, 255)
CONTORNO = (0, 0, 0, 70)
_IMAGENS: dict = {}

# Geometria em unidades de 0–64 (o SVG usa viewBox 0 0 64 64).
GEOMETRIA = {
    "raio_fundo": 14,
    "capsula": (24, 12, 40, 36),      # x0, y0, x1, y1
    "capsula_raio": 8,
    "arco": (17, 22, 47, 46),
    "arco_largura": 4,
    "haste": (30, 45, 34, 52),
    "base": (23, 51, 41, 55),
    "glifo_centro": (48, 48),
    "glifo_raio": 9,
}


def _s(v: float, escala: float) -> float:
    return v * escala


def _rect(box, escala):
    return [_s(box[0], escala), _s(box[1], escala), _s(box[2], escala), _s(box[3], escala)]


def _desenhar_glifo(d: ImageDraw.ImageDraw, estado: str | None, escala: float, cor_fundo) -> None:
    """Glifo de estado no canto inferior direito, sobre um disco da cor do estado."""
    cx, cy = GEOMETRIA["glifo_centro"]
    r = GEOMETRIA["glifo_raio"]
    if estado in (None, "aguardando"):
        return
    disco = _rect((cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2), escala)
    d.ellipse(disco, fill=cor_fundo, outline=BRANCO, width=max(1, int(2 * escala)))
    e = escala
    if estado == "transcrevendo":
        d.ellipse(_rect((cx - 4, cy - 4, cx + 4, cy + 4), e), fill=BRANCO)
    elif estado == "processando":
        for k in range(8):
            ang = k * math.pi / 4
            x0, y0 = cx + 3 * math.cos(ang), cy + 3 * math.sin(ang)
            x1, y1 = cx + 6.5 * math.cos(ang), cy + 6.5 * math.sin(ang)
            d.line([(_s(x0, e), _s(y0, e)), (_s(x1, e), _s(y1, e))], fill=BRANCO, width=max(1, int(2.2 * e)))
        d.ellipse(_rect((cx - 2, cy - 2, cx + 2, cy + 2), e), fill=BRANCO)
    elif estado == "diarizando":
        for k, h in enumerate((3, 6, 3)):
            x = cx - 4 + k * 4
            d.line([(_s(x, e), _s(cy - h, e)), (_s(x, e), _s(cy + h, e))], fill=BRANCO, width=max(1, int(2.2 * e)))
    elif estado == "pausado":
        for x in (cx - 3, cx + 3):
            d.rectangle(_rect((x - 1.3, cy - 5, x + 1.3, cy + 5), e), fill=BRANCO)
    elif estado == "erro":
        d.rectangle(_rect((cx - 1.4, cy - 6, cx + 1.4, cy + 1.5), e), fill=BRANCO)
        d.ellipse(_rect((cx - 1.6, cy + 3.2, cx + 1.6, cy + 6.4), e), fill=BRANCO)


def desenhar_icone(tamanho: int = 64, estado: str | None = None, cor_fundo=None, contorno: bool = True) -> Image.Image:
    """Renderiza o ícone em `tamanho` px; `estado` escolhe cor e glifo."""
    if cor_fundo is None:
        cor_fundo = cor_por_estado(estado) if estado else COR_AGUARDANDO
    escala = tamanho / 64.0
    # Desenha em 4x e reduz para bordas suaves nos tamanhos pequenos.
    sup = 4
    img = Image.new("RGBA", (tamanho * sup, tamanho * sup), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    e = escala * sup
    g = GEOMETRIA
    fundo = tuple(cor_fundo) + (255,) if len(cor_fundo) == 3 else tuple(cor_fundo)
    d.rounded_rectangle(_rect((2, 2, 62, 62), e), radius=_s(g["raio_fundo"], e), fill=fundo,
                        outline=CONTORNO if contorno else None, width=max(1, int(1.5 * e)) if contorno else 0)
    d.rounded_rectangle(_rect(g["capsula"], e), radius=_s(g["capsula_raio"], e), fill=BRANCO)
    d.arc(_rect(g["arco"], e), start=20, end=160, fill=BRANCO, width=max(1, int(g["arco_largura"] * e)))
    d.rectangle(_rect(g["haste"], e), fill=BRANCO)
    d.rounded_rectangle(_rect(g["base"], e), radius=_s(2, e), fill=BRANCO)
    _desenhar_glifo(d, estado, e, fundo)
    return img.resize((tamanho, tamanho), Image.LANCZOS)


def criar_imagem(cor_fundo=None, cor_mic=(255, 255, 255)):
    """Compatibilidade: desenho de 64 px sem glifo, na cor pedida."""
    return desenhar_icone(64, None, cor_fundo or COR_AGUARDANDO)


def _png_do_estado(estado: str) -> Image.Image | None:
    caminho = os.path.join(PASTA_PNG, f"{estado}.png")
    if not os.path.isfile(caminho):
        return None
    try:
        return Image.open(caminho).convert("RGBA")
    except Exception:  # noqa: BLE001 — PNG corrompido não derruba a bandeja
        return None


def imagem_por_estado(estado):
    """Ícone do estado: PNG gerado em `static/icones/bandeja/`, ou o desenho PIL."""
    if estado not in _IMAGENS:
        _IMAGENS[estado] = _png_do_estado(estado) or desenhar_icone(64, estado)
    return _IMAGENS[estado]


def criar_ico(caminho: str = ICONE_FILE, tamanhos=(16, 20, 24, 32, 48, 256)):
    """ICO multi-resolução do estado neutro (atalho, janela, instalador)."""
    quadros = [desenhar_icone(t, None) for t in tamanhos]
    quadros[-1].save(caminho, format="ICO", sizes=[(t, t) for t in tamanhos], append_images=quadros[:-1])
    return caminho
