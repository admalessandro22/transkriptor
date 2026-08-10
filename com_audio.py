# -*- coding: utf-8 -*-
"""COM viva durante toda a thread que captura áudio (FR-2.4).

O `soundcard` inicializa COM dentro de um objeto `_COMLibrary` de vida curta
cujo `__del__` chama `CoUninitialize()`. Num processo com várias threads —
bandeja, consentimento, captura, microfone, autoteste — esse par init/uninit
desbalanceia e a thread de captura fica sem COM. O sintoma em produção é:

    [INFO] Erro ao abrir audio: Error 0x800401f0   # CO_E_NOTINITIALIZED

...e a reunião inteira é gravada em branco, porque `_capturar` desiste antes de
abrir o dispositivo. O deadlock de 2026-08-07 escondia isto: a captura travava
antes de chegar aqui.

A correção é segurar uma referência COM própria pela vida inteira da thread, de
modo que o `CoUninitialize` do `soundcard` nunca leve a contagem a zero enquanto
ainda estamos gravando.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging

logger = logging.getLogger(__name__)

_COINIT_MULTITHREADED = 0x0
_S_OK = 0x00000000
_S_FALSE = 0x00000001  # já inicializada nesta thread — mesmo assim conta +1
_RPC_E_CHANGED_MODE = 0x80010106  # outra apartment; não somos donos


@contextlib.contextmanager
def com_inicializada():
    """Mantém COM inicializada no bloco. Cede `True` se nós a inicializamos.

    Nunca levanta: em máquina sem `ole32` (ou fora do Windows) apenas cede
    `False` e deixa o chamador seguir — a captura pode até falhar, mas por um
    motivo próprio, e não por causa deste utilitário.
    """
    try:
        ole32 = ctypes.windll.ole32
    except Exception:  # noqa: BLE001 — não-Windows
        yield False
        return

    try:
        hr = ole32.CoInitializeEx(None, _COINIT_MULTITHREADED) & 0xFFFFFFFF
    except Exception:  # noqa: BLE001
        logger.debug("CoInitializeEx indisponível", exc_info=True)
        yield False
        return

    if hr == _RPC_E_CHANGED_MODE:
        # A thread já pertence a outra apartment (a bandeja usa STA). Não
        # inicializamos nada, então também não podemos desinicializar.
        yield False
        return

    inicializou = hr in (_S_OK, _S_FALSE)
    if not inicializou:
        logger.debug("CoInitializeEx devolveu 0x%08x", hr)
    try:
        yield inicializou
    finally:
        if inicializou:
            with contextlib.suppress(Exception):
                ole32.CoUninitialize()
