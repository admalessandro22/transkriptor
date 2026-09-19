"""Primitivas Windows para exclusão entre processos de jobs duráveis."""
from __future__ import annotations

import ctypes
import msvcrt
import os
import time
from ctypes import wintypes
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class ProcessIdentityIndeterminate(RuntimeError):
    """A identidade de um processo não pôde ser verificada com segurança."""


class ProcessNotFound(RuntimeError):
    """O PID não existe mais."""


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    created_at_100ns: int


@dataclass(frozen=True)
class Lease:
    owner: ProcessIdentity
    nonce: str
    acquired_at_utc: str
    heartbeat_at_utc: str


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]


_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
_KERNEL32.OpenProcess.argtypes = (
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.DWORD,
)
_KERNEL32.OpenProcess.restype = wintypes.HANDLE
_KERNEL32.GetProcessTimes.argtypes = (
    wintypes.HANDLE,
    ctypes.POINTER(_FileTime),
    ctypes.POINTER(_FileTime),
    ctypes.POINTER(_FileTime),
    ctypes.POINTER(_FileTime),
)
_KERNEL32.GetProcessTimes.restype = wintypes.BOOL
_KERNEL32.CloseHandle.argtypes = (wintypes.HANDLE,)
_KERNEL32.CloseHandle.restype = wintypes.BOOL


def _created_at_100ns(pid: int) -> int:
    ctypes.set_last_error(0)
    handle = _KERNEL32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        erro = ctypes.get_last_error()
        if erro in {87, 1168}:
            raise ProcessNotFound(f"PID {pid} não existe")
        raise ProcessIdentityIndeterminate(f"não foi possível abrir PID {pid}")
    try:
        criado = _FileTime()
        saida = _FileTime()
        kernel = _FileTime()
        usuario = _FileTime()
        if not _KERNEL32.GetProcessTimes(
            handle,
            ctypes.byref(criado),
            ctypes.byref(saida),
            ctypes.byref(kernel),
            ctypes.byref(usuario),
        ):
            raise ProcessIdentityIndeterminate(
                f"não foi possível ler criação do PID {pid}"
            )
        return (criado.high << 32) | criado.low
    finally:
        _KERNEL32.CloseHandle(handle)


def current_process_identity() -> ProcessIdentity:
    pid = os.getpid()
    return ProcessIdentity(pid=pid, created_at_100ns=_created_at_100ns(pid))


def process_matches(identity: ProcessIdentity) -> bool:
    """Confere PID e criação para rejeitar reutilização de PID."""
    try:
        return _created_at_100ns(identity.pid) == identity.created_at_100ns
    except ProcessNotFound:
        return False


@contextmanager
def job_lock(lock_path: Path, timeout_s: float = 5.0) -> Iterator[None]:
    """Adquire um byte de lock com timeout, sem depender de lock Python."""
    if timeout_s <= 0:
        raise ValueError("timeout de lock deve ser positivo")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + timeout_s
    arquivo = None
    while True:
        try:
            arquivo = lock_path.open("a+b")
            arquivo.seek(0)
            if not arquivo.read(1):
                arquivo.seek(0)
                arquivo.write(b"\0")
                arquivo.flush()
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            break
        except OSError:
            if arquivo is not None:
                arquivo.close()
                arquivo = None
            if time.monotonic() >= limite:
                raise TimeoutError(f"timeout ao bloquear {lock_path.name}")
            time.sleep(0.01)
    try:
        yield
    finally:
        try:
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            arquivo.close()
