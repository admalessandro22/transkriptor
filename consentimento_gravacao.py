# -*- coding: utf-8 -*-
"""Consentimento explícito e fail-closed antes da captura de reunião."""
from __future__ import annotations

import logging

from config import TIMEOUT_AVISO_GRAVACAO_SEG
from transkriptor_acoes import resposta_autoriza_gravacao

logger = logging.getLogger(__name__)


def _mostrar_dialogo(timeout_seg: int) -> int:
    import ctypes
    from ctypes import wintypes

    funcao = ctypes.windll.user32.MessageBoxTimeoutW
    funcao.argtypes = [
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.UINT,
        wintypes.WORD,
        wintypes.DWORD,
    ]
    funcao.restype = ctypes.c_int
    # YESNO | SETFOREGROUND | TOPMOST. Sem ícone sonoro de pergunta.
    opcoes = 0x4 | 0x10000 | 0x40000
    return int(
        funcao(
            None,
            "O Transkriptor detectou uma reunião.\n\n"
            "Quer gravar o áudio e gerar a transcrição em texto?\n\n"
            "A captura só começa depois de escolher Sim.\n"
            "Não ou ausência de resposta não gravam esta reunião.",
            "Transkriptor — confirmar gravação",
            opcoes,
            0,
            max(1, int(timeout_seg)) * 1000,
        )
    )


def pedir_consentimento(timeout_seg: int = TIMEOUT_AVISO_GRAVACAO_SEG) -> bool:
    """Retorna True exclusivamente para a resposta Sim do diálogo."""
    try:
        return resposta_autoriza_gravacao(_mostrar_dialogo(timeout_seg))
    except Exception:
        logger.exception("Diálogo de consentimento indisponível; captura bloqueada")
        return False
