# -*- coding: utf-8 -*-
"""Notificações nativas do Windows (toasts).

Usa plyer como primário (mais robusto) com fallback para win10toast
e finalmente para log apenas se ambos falharem.
"""

import logging

from status_seguro import sanitizar_toast_para_log

logger = logging.getLogger(__name__)

PREFIXOS_SEM_TOAST_AO_VIVO = ("Watchdog", "Carregando", "ERRO")
LIMITE_CHARS_TOAST_AO_VIVO = 60
MIN_CHARS_TOAST_AO_VIVO = 10

# "plyer" | "win10toast" | "none" | None (ainda não detectado)
_backend = None


def formatar_mensagem_toast(mensagem, max_len=LIMITE_CHARS_TOAST_AO_VIVO):
    if len(mensagem) <= max_len:
        return mensagem
    return mensagem[:max_len] + "..."


def meet_em_foco(titulo_janela_ativa, titulo_eh_meet_fn):
    if not titulo_janela_ativa or not str(titulo_janela_ativa).strip():
        return False
    return titulo_eh_meet_fn(str(titulo_janela_ativa).strip())


def deve_toast_ao_vivo(mensagem, meet_em_foco, transcricao_ativa):
    if not mensagem or not transcricao_ativa:
        return False
    if mensagem.startswith(PREFIXOS_SEM_TOAST_AO_VIVO):
        return False
    if meet_em_foco:
        return False
    return len(mensagem) > MIN_CHARS_TOAST_AO_VIVO


def _detectar_backend():
    global _backend
    if _backend is not None:
        return _backend
    try:
        import plyer  # noqa
        _backend = "plyer"
        return _backend
    except Exception:
        pass
    try:
        import win10toast  # noqa
        _backend = "win10toast"
        return _backend
    except Exception:
        pass
    _backend = "none"
    return _backend


def notificar(titulo, mensagem, duracao=5, icone=None):
    """Mostra uma notificação toast do Windows.

    Se nenhum backend estiver disponível, registra no log apenas.
    """
    global _backend
    b = _detectar_backend()

    if b == "plyer":
        try:
            from plyer import notification
            notification.notify(
                title=titulo,
                message=mensagem,
                app_name="Transkriptor",
                timeout=duracao,
            )
            logger.info(sanitizar_toast_para_log(titulo, mensagem))
            return
        except Exception as e:
            logger.warning(f"plyer falhou: {e}. Tentando win10toast.")
            _backend = "win10toast"
            b = "win10toast"

    if b == "win10toast":
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(
                titulo, mensagem, duration=duracao, icon_path=icone, threaded=True
            )
            logger.info(sanitizar_toast_para_log(titulo, mensagem))
            return
        except Exception as e:
            logger.warning(f"win10toast falhou: {e}. Log apenas.")
            _backend = "none"
            b = "none"

    logger.info(sanitizar_toast_para_log(titulo, mensagem))
