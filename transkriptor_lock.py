# -*- coding: utf-8 -*-
"""Mutex de instância única do Transkriptor.

Duas camadas, por ordem de confiabilidade:

1. **Mutex nomeado do Windows** — o kernel libera sozinho quando o processo
   morre, mesmo se for morto à força. É a fonte da verdade.
2. **Arquivo de lock com PID** — compatibilidade e diagnóstico.

A camada 1 existe porque a 2, sozinha, trava o app: se o Transkriptor for
encerrado à força, o arquivo sobrevive e o Windows pode reciclar aquele PID para
outro processo qualquer. O app então recusava iniciar para sempre, dizendo "já
está em execução" — sem ícone na bandeja e sem gravar nada.
"""
import logging
import os
import sys

logger = logging.getLogger(__name__)

NOME_MUTEX = "Global\\TranskriptorInstanciaUnica"
_ERROR_ALREADY_EXISTS = 183

_handles = []
_mutex_handle = None


def _adquirir_mutex_nomeado(nome=NOME_MUTEX):
    """(adquiriu, handle). `adquiriu=False` só quando outra instância vive."""
    if sys.platform != "win32":
        return True, None
    try:
        import ctypes
        from ctypes import wintypes

        criar = ctypes.windll.kernel32.CreateMutexW
        criar.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        criar.restype = wintypes.HANDLE
        handle = criar(None, True, nome)
        if not handle:
            return True, None  # sem mutex disponível: não bloquear o app
        if ctypes.windll.kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
            ctypes.windll.kernel32.CloseHandle(handle)
            return False, None
        return True, handle
    except Exception:  # noqa: BLE001
        logger.debug("Mutex nomeado indisponível", exc_info=True)
        return True, None


def _liberar_mutex_nomeado():
    global _mutex_handle
    if _mutex_handle is None:
        return
    try:
        import ctypes

        ctypes.windll.kernel32.ReleaseMutex(_mutex_handle)
        ctypes.windll.kernel32.CloseHandle(_mutex_handle)
    except Exception:  # noqa: BLE001
        logger.debug("Falha ao liberar mutex nomeado", exc_info=True)
    _mutex_handle = None


def _pid_vivo(pid):
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            consultou = ctypes.windll.kernel32.GetExitCodeProcess(
                handle,
                ctypes.byref(exit_code),
            )
            ctypes.windll.kernel32.CloseHandle(handle)
            if not consultou:
                return True
            return exit_code.value == STILL_ACTIVE
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _lock_ocupado_por_outro(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = (f.read() or "").strip()
    except OSError:
        return True
    if not raw:
        return True
    try:
        pid = int(raw)
    except ValueError:
        return True
    return _pid_vivo(pid)


def _remover_lock_obsoleto(path):
    if _lock_ocupado_por_outro(path):
        return False
    try:
        os.remove(path)
    except OSError:
        return False
    return True


def _forcar_remocao_lock(path):
    """Remove um lock cujo dono não existe mais (o mutex já provou isso)."""
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def adquirir_lock(caminho, usar_mutex_nomeado=False):
    """Tenta lock exclusivo. Retorna False se outra instância já detém.

    Com `usar_mutex_nomeado=True` (o app real), o mutex do kernel decide: se ele
    foi concedido, nenhuma outra instância existe e um arquivo de lock
    remanescente é apenas lixo de um encerramento forçado.
    """
    global _mutex_handle
    path = os.fspath(caminho)
    if usar_mutex_nomeado:
        adquiriu, handle = _adquirir_mutex_nomeado()
        if not adquiriu:
            return False
        _mutex_handle = handle
        if handle is not None and os.path.exists(path):
            logger.info("Lock órfão de encerramento forçado removido: %s", path)
            _forcar_remocao_lock(path)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            if not _remover_lock_obsoleto(path):
                _liberar_mutex_nomeado()
                return False
            continue
        f = os.fdopen(fd, "w+b")
        f.write(str(os.getpid()).encode("ascii"))
        f.flush()
        _handles.append((f, path))
        return True
    _liberar_mutex_nomeado()
    return False


def liberar_lock():
    _liberar_mutex_nomeado()
    for f, path in _handles:
        try:
            f.close()
        except OSError:
            pass
        try:
            os.remove(path)
        except OSError:
            pass
    _handles.clear()
