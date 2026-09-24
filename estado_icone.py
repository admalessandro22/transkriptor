# -*- coding: utf-8 -*-
"""Resolução pura de estado/cor do ícone da bandeja."""

import time

# Cores do ícone vêm da fonte única de tokens (design/tokens.json → design_tokens.py),
# as mesmas usadas pela Central. Ver SDD v1.9, T-14.A1.
from design_tokens import (
    COR_AGUARDANDO,
    COR_DIARIZANDO,
    COR_ERRO,
    COR_PAUSADO,
    COR_PROCESSANDO,
    COR_TRANSCREVENDO,
)

DURACAO_ERRO_ICONE = 30

_CORES = {
    "aguardando": COR_AGUARDANDO,
    "transcrevendo": COR_TRANSCREVENDO,
    "diarizando": COR_DIARIZANDO,
    "processando": COR_PROCESSANDO,
    "erro": COR_ERRO,
    "pausado": COR_PAUSADO,
}


def erro_icone_expirado(instante_erro, agora, duracao=DURACAO_ERRO_ICONE):
    return (agora - instante_erro) >= duracao


def resolver_estado_icone(
    transcritor,
    deteccao_ativa,
    em_erro=False,
    instante_erro=None,
    agora=None,
    processando=False,
):
    agora = time.monotonic() if agora is None else agora
    # Títulos do tooltip seguem o glossário da Central (UX-14.E2).
    if em_erro:
        if instante_erro is None or not erro_icone_expirado(instante_erro, agora):
            return "erro", "Erro"
    if transcritor and getattr(transcritor, "diarizando", False):
        return "diarizando", "Separando vozes"
    if transcritor and getattr(transcritor, "rodando", False):
        return "transcrevendo", "Gravando"
    if processando:
        return "processando", "Processando reunião"
    if deteccao_ativa:
        return "aguardando", "Aguardando reunião"
    return "pausado", "Pausado · não grava reuniões"


def cor_por_estado(estado):
    return _CORES.get(estado, COR_AGUARDANDO)
