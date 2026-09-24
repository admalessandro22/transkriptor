# -*- coding: utf-8 -*-
"""Captura a confirmação real da bandeja (MessageBoxW) para "pausar_gravacao" (T-14.E4).

    python docs/sdd/v1.9/evidencias/T-14.E4/capturar_bandeja.py

Abre `confirmacoes.confirmar_na_bandeja` numa thread, fotografa a caixa pelo
título com PIL.ImageGrab e responde "Não" por WM_COMMAND — nada é pausado.
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

from PIL import ImageGrab  # noqa: E402

import confirmacoes  # noqa: E402
from consentimento_controles import ativar_dpi_na_thread, restaurar_dpi_na_thread  # noqa: E402

DESTINO = Path(__file__).resolve().parent
WM_COMMAND = 0x0111
IDNO = 7


def main() -> int:
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    # Coordenadas físicas: a thread que mede precisa ser ciente de DPI (como em E3).
    dpi_anterior = ativar_dpi_na_thread(user32)
    resultado = {}
    fio = threading.Thread(target=lambda: resultado.setdefault("ok", confirmacoes.confirmar_na_bandeja("pausar_gravacao")), daemon=True)
    fio.start()
    hwnd = None
    for _ in range(100):
        hwnd = user32.FindWindowW("#32770", confirmacoes.TITULO_BANDEJA)
        if hwnd:
            break
        time.sleep(0.05)
    if not hwnd:
        print("caixa não encontrada")
        return 1
    time.sleep(0.8)  # animação de abertura concluída
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)
    user32.PostMessageW(hwnd, WM_COMMAND, IDNO, 0)
    fio.join(timeout=5)
    restaurar_dpi_na_thread(user32, dpi_anterior)
    nome = DESTINO / "bandeja-pausar-messagebox.png"
    img.save(nome)
    print(f"{nome.name}: {img.size[0]}x{img.size[1]} px, confirmou={resultado.get('ok')} (Não = nada muda)")
    return 0 if resultado.get("ok") is False else 1


if __name__ == "__main__":
    raise SystemExit(main())
