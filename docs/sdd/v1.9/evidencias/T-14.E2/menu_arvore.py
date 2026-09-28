# -*- coding: utf-8 -*-
"""Imprime a árvore do menu da bandeja montada por `MenuBandejaMixin._menu()` com um app sintético.

    python docs/sdd/v1.9/evidencias/T-14.E2/menu_arvore.py > docs/sdd/v1.9/evidencias/T-14.E2/menu-arvore.txt

Não inicia a bandeja nem lê dados reais: só constrói o `pystray.Menu` e o percorre.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

import pystray  # noqa: E402

from app_bandeja_menu import MenuBandejaMixin  # noqa: E402


class AppSintetico(MenuBandejaMixin):
    transcritor = None
    deteccao_ativa = True
    diarizacao_ativa = True
    identificar_minha_voz = False
    usar_nomes_meet = True
    modo_legendas_meet = False
    criptografar_transcricoes = True
    iniciar_com_windows = False
    modelo_whisper = "auto"
    rotulo_usuario = "VOCÊ"
    _estado_processamento = None
    detector = SimpleNamespace(fontes_da_reuniao=[], instantaneo=lambda: [])


def percorrer(menu, nivel=0):
    for item in menu:
        if item is pystray.Menu.SEPARATOR:
            print("  " * nivel + "──────────")
            continue
        texto = item.text  # str(item) já embute o submenu
        marca = ""
        try:
            if item.checked is not None:
                marca = " [x]" if item.checked else " [ ]"
        except Exception:  # noqa: BLE001
            marca = ""
        padrao = " (padrão)" if getattr(item, "default", False) else ""
        print("  " * nivel + f"{texto}{marca}{padrao}")
        if item.submenu is not None:
            percorrer(item.submenu, nivel + 1)


if __name__ == "__main__":
    percorrer(AppSintetico()._menu())
