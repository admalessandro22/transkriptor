# -*- coding: utf-8 -*-
"""Gerado por scripts/gerar_tokens.py a partir de design/tokens.json. Não editar à mão."""

VERSAO_TOKENS = 1

COR_AGUARDANDO = (91, 107, 140)
COR_TRANSCREVENDO = (34, 197, 94)
COR_DIARIZANDO = (245, 158, 11)
COR_PROCESSANDO = (139, 92, 246)
COR_ERRO = (239, 68, 68)
COR_PAUSADO = (100, 116, 139)

ESTADOS = {
    'idle': (91, 107, 140),
    'recording': (34, 197, 94),
    'processing': (139, 92, 246),
    'diarizing': (245, 158, 11),
    'paused': (100, 116, 139),
    'error': (239, 68, 68),
}
