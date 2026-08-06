# -*- coding: utf-8 -*-
"""Resolução pura de estado/cor do ícone da bandeja."""

import time

COR_AGUARDANDO = (30, 41, 59)
COR_TRANSCREVENDO = (34, 197, 94)
COR_DIARIZANDO = (201, 169, 97)
COR_PROCESSANDO = (139, 92, 246)
COR_ERRO = (239, 68, 68)
COR_PAUSADO = (100, 116, 139)  # #64748b

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
    if em_erro:
        if instante_erro is None or not erro_icone_expirado(instante_erro, agora):
            return "erro", "Erro"
    if transcritor and getattr(transcritor, "diarizando", False):
        return "diarizando", "Separando vozes..."
    if transcritor and getattr(transcritor, "rodando", False):
        return "transcrevendo", "Transcrevendo"
    if processando:
        return "processando", "Processando reunião..."
    if deteccao_ativa:
        return "aguardando", "Aguardando Meet"
    return "pausado", "PAUSADO — não está gravando"


def cor_por_estado(estado):
    return _CORES.get(estado, COR_AGUARDANDO)
