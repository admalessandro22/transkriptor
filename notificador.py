# -*- coding: utf-8 -*-
"""Notificações silenciosas que reutilizam o único ícone da bandeja."""
from __future__ import annotations

import logging
import threading

from status_seguro import sanitizar_toast_para_log

logger = logging.getLogger(__name__)

_icone_bandeja = None
_lock = threading.Lock()


def configurar_icone(icone) -> None:
    """Registra o ícone pystray já criado pelo processo principal."""
    global _icone_bandeja
    with _lock:
        _icone_bandeja = icone


def notificar(titulo, mensagem, visivel=False) -> bool:
    """Registra silenciosamente; só mostra balão quando solicitado explicitamente."""
    logger.info(sanitizar_toast_para_log(titulo, mensagem))
    if not visivel:
        return False
    with _lock:
        icone = _icone_bandeja
    if icone is None:
        logger.warning("Notificação visível ignorada: bandeja ainda indisponível")
        return False
    try:
        icone.notify(mensagem, titulo)
        return True
    except Exception:
        logger.warning("Notificação nativa da bandeja indisponível", exc_info=True)
        return False
