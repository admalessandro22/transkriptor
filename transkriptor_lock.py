# -*- coding: utf-8 -*-
"""Mutex de instância única do Transkriptor."""
import os
import sys

_handles = []


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


def adquirir_lock(caminho):
    """Tenta lock exclusivo. Retorna False se outra instância já detém."""
    global _handles
    path = os.fspath(caminho)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            if not _remover_lock_obsoleto(path):
                return False
            continue
        f = os.fdopen(fd, "w+b")
        f.write(str(os.getpid()).encode("ascii"))
        f.flush()
        _handles.append((f, path))
        return True
    return False


def liberar_lock():
    global _handles
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
