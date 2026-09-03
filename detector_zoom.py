# -*- coding: utf-8 -*-
"""Reunião do Zoom reconhecida sem depender do texto da janela (FR-10.A3).

O título do Zoom muda com o idioma (`Zoom Meeting`, `Reunião Zoom`) e, nas
versões 6.x, a chamada pode acontecer dentro da janela `Zoom Workplace` — o
mesmo nome da janela ociosa. Depender só de regex deixava o Zoom invisível para
o detector, e `zoom.exe` segurando o microfone não resolve sozinho porque
microfone é sinal auxiliar (FR-10.A1).

Duas rotas independentes, ambas fortes:

1. **classe da janela** — o Windows dá à janela de chamada uma classe própria,
   estável entre idiomas e versões;
2. **microfone + janela do Zoom** — `zoom.exe` só abre o microfone em chamada;
   exigir uma janela do Zoom junto evita o caso do microfone de outro app.

`listar_janelas_com_classe` é a única parte que fala com o Windows; toda a
decisão vive em funções puras, testadas sem o Zoom instalado.
"""

from __future__ import annotations

import ctypes
import logging
import re
from ctypes import wintypes
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Classes da janela de chamada do Zoom. Nomes estáveis há várias versões, mas
# validáveis na máquina do usuário: o Diagnóstico da bandeja lista título+classe
# de toda janela do Zoom aberta (ver `diagnostico.checar_zoom`).
CLASSES_REUNIAO_ZOOM = (
    "ZPContentViewWndClass",  # janela da chamada (5.x/6.x)
    "ConferenceWindowClass",  # janela da chamada (legado)
    "ZPFloatVideoWndClass",  # vídeo flutuante da chamada minimizada
)

# Classes de qualquer janela do Zoom, inclusive ociosa. Serve para corroborar o
# microfone, nunca para iniciar sozinha.
_PREFIXOS_CLASSE_ZOOM = ("ZP", "Zoom", "Conference")

_EXECUTAVEL_ZOOM = "zoom.exe"


@dataclass(frozen=True)
class Janela:
    """Uma janela de topo, como o detector precisa vê-la."""

    titulo: str = ""
    classe: str = ""
    visivel: bool = True


# Título de janela **do app** Zoom. Deliberadamente ancorado: só mencionar
# "zoom" não basta — um terminal, um documento ou uma aba de navegador falando
# sobre Zoom apareceriam como janela do Zoom (visto em varredura real).
_TITULO_APP_ZOOM = re.compile(
    r"^\s*Zoom(?:\s+(?:Workplace|Meeting|Webinar|Reuni[aã]o))?\s*$"
    r"|^\s*Reuni[aã]o\s+(?:do\s+)?Zoom\s*$",
    re.IGNORECASE,
)


def janela_e_do_zoom(janela: Janela) -> bool:
    """True para uma janela **do app** Zoom, em chamada ou não."""
    classe = str(janela.classe or "")
    if classe and classe.startswith(_PREFIXOS_CLASSE_ZOOM):
        return True
    return bool(_TITULO_APP_ZOOM.match(str(janela.titulo or "")))


def janela_e_chamada_do_zoom(janela: Janela) -> bool:
    """True só para a janela que o Zoom cria durante uma chamada."""
    return str(janela.classe or "") in CLASSES_REUNIAO_ZOOM


def zoom_em_reuniao(janelas, apps_com_microfone) -> tuple[bool, str]:
    """Decide se há chamada do Zoom agora. Função pura: é ela que os testes usam.

    Devolve `(ativo, motivo)`; `motivo` vai para o Diagnóstico da bandeja para
    o usuário saber por que a gravação começou.
    """
    lista = list(janelas or [])
    if any(janela_e_chamada_do_zoom(j) for j in lista):
        return (True, "classe da janela do Zoom")

    microfones = {str(a).lower() for a in (apps_com_microfone or [])}
    if _EXECUTAVEL_ZOOM in microfones and any(janela_e_do_zoom(j) for j in lista):
        return (True, "microfone do Zoom com janela aberta")

    return (False, "")


def listar_janelas_com_classe() -> list[Janela]:
    """Janelas de topo com título **e** classe — o pygetwindow não dá a classe."""
    user32 = ctypes.windll.user32
    janelas: list[Janela] = []

    enum_proc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )

    def _callback(hwnd, _lparam):
        try:
            tamanho = user32.GetWindowTextLengthW(hwnd)
            texto = ctypes.create_unicode_buffer(tamanho + 1)
            user32.GetWindowTextW(hwnd, texto, tamanho + 1)
            classe = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, classe, 256)
            janelas.append(
                Janela(
                    titulo=texto.value,
                    classe=classe.value,
                    visivel=bool(user32.IsWindowVisible(hwnd)),
                )
            )
        except Exception:  # noqa: BLE001 — uma janela ruim não derruba a varredura
            logger.debug("Falha ao ler janela", exc_info=True)
        return True

    try:
        user32.EnumWindows(enum_proc(_callback), 0)
    except Exception:  # noqa: BLE001 — fonte auxiliar nunca derruba o monitor
        logger.debug("EnumWindows falhou", exc_info=True)
    return janelas


def janelas_do_zoom() -> list[Janela]:
    """Só as janelas do Zoom — usado pelo Diagnóstico para validar as classes."""
    return [j for j in listar_janelas_com_classe() if janela_e_do_zoom(j)]
