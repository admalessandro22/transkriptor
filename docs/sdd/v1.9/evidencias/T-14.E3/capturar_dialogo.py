# -*- coding: utf-8 -*-
"""Captura o diálogo de consentimento real em 100/150/200 % (T-14.E3).

    python docs/sdd/v1.9/evidencias/T-14.E3/capturar_dialogo.py

Abre `_mostrar_dialogo` com timeout curto e DPI forçado (96/144/192), fotografa
a janela pelo título com PIL.ImageGrab e deixa o timeout fechar como "Não
gravar" — nenhum consentimento é dado e nada é gravado. Fontes sintéticas.
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(RAIZ))

from PIL import Image, ImageGrab  # noqa: E402

import consentimento_gravacao as cg  # noqa: E402

DESTINO = Path(__file__).resolve().parent
CENARIOS = [(96, ("titulo",)), (144, ("titulo", "microfone")), (192, ("zoom",))]


def _capturar(dpi: int) -> Image.Image | None:
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    anterior = cg.ativar_dpi_na_thread(user32)
    try:
        for _ in range(60):
            hwnd = user32.FindWindowW(None, cg.TITULO_DIALOGO)
            if hwnd:
                break
            time.sleep(0.05)
        else:
            return None
        time.sleep(1.2)  # deixa a contagem andar para a barra aparecer parcial
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)
    finally:
        cg.restaurar_dpi_na_thread(user32, anterior)


def main() -> int:
    for dpi, fontes in CENARIOS:
        resultado = {}
        alvo = threading.Thread(target=lambda: resultado.setdefault("img", _capturar(dpi)), daemon=True)
        alvo.start()
        valor = cg._mostrar_dialogo(3, fontes=fontes, dpi=dpi)
        alvo.join(timeout=5)
        img = resultado.get("img")
        if img is None:
            print(f"{dpi}: janela não encontrada")
            return 1
        nome = DESTINO / f"consentimento-{int(dpi / 96 * 100)}pct.png"
        img.save(nome)
        print(f"{nome.name}: {img.size[0]}x{img.size[1]} px, resposta={valor} (timeout = não gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
