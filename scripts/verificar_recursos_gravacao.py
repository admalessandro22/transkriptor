#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede recursos da bandeja durante gravação sem ler títulos ou áudio."""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import time
from ctypes import wintypes


LIMITE_CRESCIMENTO_MEMORIA_MB = 100.0
LIMITE_CPU_MEDIA_PCT = 10.0
ICONE_ESPERADO = 1


def _amostras_validas(valores, nome):
    amostras = [float(valor) for valor in valores]
    if not amostras or any(not math.isfinite(v) or v < 0 for v in amostras):
        raise ValueError(f"amostras inválidas: {nome}")
    return amostras


def avaliar(amostras_memoria_mb, amostras_cpu, amostras_icones=(1,)) -> dict:
    """Avalia NFR-10.C2; CPU é percentual de um núcleo, não do sistema."""
    memoria = _amostras_validas(amostras_memoria_mb, "memoria")
    cpu = _amostras_validas(amostras_cpu, "cpu")
    icones = _amostras_validas(amostras_icones, "icones")
    crescimento = max(memoria) - min(memoria)
    cpu_media = sum(cpu) / len(cpu)
    icones_ok = all(int(valor) == ICONE_ESPERADO for valor in icones)
    memoria_ok = crescimento < LIMITE_CRESCIMENTO_MEMORIA_MB
    cpu_ok = cpu_media < LIMITE_CPU_MEDIA_PCT
    return {
        "ok": memoria_ok and cpu_ok and icones_ok,
        "crescimento_memoria_mb": round(crescimento, 3),
        "cpu_media_pct_um_nucleo": round(cpu_media, 3),
        "icones_observados": [int(valor) for valor in icones],
        "checks": {
            "memoria": memoria_ok,
            "cpu": cpu_ok,
            "icones": icones_ok,
        },
        "limites": {
            "crescimento_memoria_mb": LIMITE_CRESCIMENTO_MEMORIA_MB,
            "cpu_media_pct_um_nucleo": LIMITE_CPU_MEDIA_PCT,
            "icones": ICONE_ESPERADO,
        },
    }


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _filetime_segundos(valor) -> float:
    ticks = (int(valor.dwHighDateTime) << 32) | int(valor.dwLowDateTime)
    return ticks / 10_000_000.0


def _recursos_processo(pid: int) -> tuple[float, float]:
    if os.name != "nt":
        raise RuntimeError("gate de recursos disponível apenas no Windows")
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x0410, False, int(pid))
    if not handle:
        raise ProcessLookupError(pid)
    try:
        memoria = _PROCESS_MEMORY_COUNTERS()
        memoria.cb = ctypes.sizeof(memoria)
        if not psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(memoria), ctypes.sizeof(memoria)
        ):
            raise OSError("GetProcessMemoryInfo falhou")
        criacao, saida, kernel, usuario = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(criacao),
            ctypes.byref(saida),
            ctypes.byref(kernel),
            ctypes.byref(usuario),
        ):
            raise OSError("GetProcessTimes falhou")
        cpu_seg = _filetime_segundos(kernel) + _filetime_segundos(usuario)
        return memoria.WorkingSetSize / (1024**2), cpu_seg
    finally:
        kernel32.CloseHandle(handle)


def _contar_icones_pystray(pid: int) -> int:
    """Conta classes pystray únicas do PID; cada ícone cria duas janelas iguais."""
    if os.name != "nt":
        raise RuntimeError("contagem de ícones disponível apenas no Windows")
    classes = set()
    user32 = ctypes.windll.user32
    callback_tipo = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_tipo
    def visitar(hwnd, _lparam):
        pid_janela = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_janela))
        if pid_janela.value == int(pid):
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buffer, len(buffer))
            if buffer.value.endswith("SystemTrayIcon"):
                classes.add(buffer.value)
        return True

    user32.EnumWindows(visitar, 0)
    return len(classes)


def amostrar(pid: int, duracao_seg=600.0, intervalo_seg=5.0, aquecimento_seg=30.0):
    """Coleta working set, CPU de um núcleo e quantidade de ícones do PID."""
    if duracao_seg <= 0 or intervalo_seg <= 0 or aquecimento_seg < 0:
        raise ValueError("duração, intervalo e aquecimento inválidos")
    if aquecimento_seg:
        time.sleep(aquecimento_seg)
    memoria_inicial, cpu_anterior = _recursos_processo(pid)
    memoria = [memoria_inicial]
    cpu = []
    icones = [_contar_icones_pystray(pid)]
    inicio = anterior = time.monotonic()
    while time.monotonic() - inicio < duracao_seg:
        restante = duracao_seg - (time.monotonic() - inicio)
        time.sleep(min(intervalo_seg, restante))
        agora = time.monotonic()
        memoria_atual, cpu_atual = _recursos_processo(pid)
        delta = max(agora - anterior, 1e-6)
        cpu.append(max(0.0, cpu_atual - cpu_anterior) / delta * 100.0)
        memoria.append(memoria_atual)
        icones.append(_contar_icones_pystray(pid))
        anterior, cpu_anterior = agora, cpu_atual
    return memoria, cpu, icones


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gate de recursos da gravação v1.5")
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--duracao", type=float, default=600.0)
    parser.add_argument("--intervalo", type=float, default=5.0)
    parser.add_argument("--aquecimento", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        amostras = amostrar(
            args.pid,
            duracao_seg=args.duracao,
            intervalo_seg=args.intervalo,
            aquecimento_seg=args.aquecimento,
        )
        resultado = avaliar(*amostras)
    except Exception as exc:
        resultado = {"ok": False, "erro": type(exc).__name__}
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
