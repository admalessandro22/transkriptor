# -*- coding: utf-8 -*-
"""Layout puro do diálogo de consentimento (UX-14.E3).

Tudo aqui é testável sem janela: geometria escalada por DPI, textos fixos e a
descrição das fontes detectadas. A fonte detectada só sai de uma lista fixa de
rótulos — nunca título de janela nem nome de participante (SEC-14).
"""
from __future__ import annotations

from typing import Iterable

from config import (
    CONSENTIMENTO_BOTAO_ALTURA_MIN,
    CONSENTIMENTO_DPI_BASE,
    CONSENTIMENTO_ICONE_BASE,
    CONSENTIMENTO_LARGURA_BASE,
    CONSENTIMENTO_MARGEM_BASE,
)

TITULO_PERGUNTA = "Gravar esta reunião?"
# Duas linhas curtas: cabem em 476 px a 15 px (Segoe UI) sem quebra extra.
MENSAGEM = (
    "O áudio vira transcrição em texto, guardada só neste computador.\r\n"
    "Só começa depois de escolher Gravar. Sem resposta, não grava."
)
TEXTO_SIM = "Gravar esta reunião"
TEXTO_NAO = "Não gravar"
DICA = "Nada é gravado antes da sua escolha. Áudio e texto ficam em transcrições/."

# Rótulos por fonte do detector (deteccao_reuniao.*.nome). Qualquer outra string é ignorada.
ROTULOS_FONTES = {
    "titulo": "Google Meet",
    "extensao": "Google Meet",
    "zoom": "Zoom",
    "microfone": "microfone em uso",
}

_FONTES_PX = {"titulo": 20, "corpo": 15, "pequena": 12}
# Geometria base (96 dpi): x, y, largura, altura. Margem 22, largura útil 476.
_BASE = {
    "icone": (22, 20, CONSENTIMENTO_ICONE_BASE, CONSENTIMENTO_ICONE_BASE),
    "titulo": (66, 22, 432, 28),
    "mensagem": (22, 64, 476, 62),
    "fonte_detectada": (22, 134, 476, 20),
    "progresso": (22, 164, 476, 8),
    "contagem": (22, 178, 476, 18),
    "botao_sim": (22, 208, 232, CONSENTIMENTO_BOTAO_ALTURA_MIN + 2),
    "botao_nao": (266, 208, 136, CONSENTIMENTO_BOTAO_ALTURA_MIN),
    "dica": (22, 258, 476, 16),
}
_ALTURA_BASE = 292


def layout_consentimento(dpi: int) -> dict:
    """Posições e tamanhos (px físicos) do diálogo para o DPI informado.

    DPI inválido cai em 96. Todos os valores são inteiros; a escala é `dpi/96`.
    """
    try:
        dpi = int(dpi)
    except (TypeError, ValueError):
        dpi = CONSENTIMENTO_DPI_BASE
    if dpi <= 0:
        dpi = CONSENTIMENTO_DPI_BASE
    escala = dpi / CONSENTIMENTO_DPI_BASE

    def px(valor: int) -> int:
        return int(round(valor * escala))

    layout: dict = {
        "dpi": dpi,
        "escala": escala,
        "margem": px(CONSENTIMENTO_MARGEM_BASE),
        "janela": {"largura": px(CONSENTIMENTO_LARGURA_BASE), "altura": px(_ALTURA_BASE)},
        "fontes": {nome: px(tamanho) for nome, tamanho in _FONTES_PX.items()},
    }
    for nome, (x, y, largura, altura) in _BASE.items():
        layout[nome] = {"x": px(x), "y": px(y), "largura": px(largura), "altura": px(altura)}
    return layout


def descrever_fontes(fontes: Iterable[str]) -> str:
    """Linha "Detectado: …" só com rótulos conhecidos, sem repetição e na ordem do detector."""
    rotulos: list[str] = []
    for fonte in fontes or ():
        rotulo = ROTULOS_FONTES.get(str(fonte))
        if rotulo and rotulo not in rotulos:
            rotulos.append(rotulo)
    if not rotulos:
        return "Reunião detectada"
    return "Detectado: " + ", ".join(rotulos)


def texto_contagem(restante_seg: int) -> str:
    return f"Fecha em {max(0, int(restante_seg))} s sem gravar"
