# -*- coding: utf-8 -*-
"""Controles Win32 do diálogo de consentimento (UX-14.E3).

Cria título, mensagem, fonte detectada, barra de progresso (`msctls_progress32`),
contagem, botões e dica a partir de `consentimento_layout.layout_consentimento`.
Cada recurso novo (DPI por thread, ícone, barra) falha em silêncio e cai no
comportamento anterior; IDs de controle e o `WNDPROC` ficam em
`consentimento_gravacao.py`.
"""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

from config import ICONE_FILE
from consentimento_layout import (
    DICA,
    MENSAGEM,
    TEXTO_NAO,
    TEXTO_SIM,
    TITULO_PERGUNTA,
    descrever_fontes,
    layout_consentimento,
    texto_contagem,
)

logger = logging.getLogger(__name__)

WM_SETFONT = 0x0030
STM_SETICON = 0x0170
PBM_SETRANGE32 = 0x0406
PBM_SETPOS = 0x0402
_SS_ICON = 0x00000003
_SS_LEFT = 0x00000000
_SS_NOPREFIX = 0x00000080
_WS_CHILD = 0x40000000
_WS_VISIBLE = 0x10000000
_WS_TABSTOP = 0x00010000
_BS_DEFPUSHBUTTON = 0x00000001
_ICC_PROGRESS_CLASS = 0x00000020
_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4


class _INITCOMMONCONTROLSEX(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("dwICC", wintypes.DWORD)]


def ativar_dpi_na_thread(user32):
    """Torna só a thread do diálogo ciente de DPI (Win10 1703+). Falha → None."""
    try:
        user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        return user32.SetThreadDpiAwarenessContext(
            ctypes.c_void_p(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        )
    except Exception:  # noqa: BLE001
        return None


def restaurar_dpi_na_thread(user32, anterior) -> None:
    if anterior:
        try:
            user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(anterior))
        except Exception:  # noqa: BLE001
            pass


def dpi_do_sistema(user32) -> int:
    try:
        user32.GetDpiForSystem.restype = wintypes.UINT
        dpi = int(user32.GetDpiForSystem())
        return dpi if dpi > 0 else 96
    except Exception:  # noqa: BLE001
        return 96


def carregar_icone(user32, tamanho: int):
    """Ícone do produto (transkriptor.ico) no tamanho pedido; None se faltar."""
    try:
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        return user32.LoadImageW(None, ICONE_FILE, _IMAGE_ICON, tamanho, tamanho, _LR_LOADFROMFILE) or None
    except Exception:  # noqa: BLE001
        return None


def ajustar_janela(user32, largura: int, altura: int, estilo: int, estilo_ex: int) -> tuple[int, int]:
    """Área do cliente → tamanho da janela com moldura e barra de título."""
    try:
        rect = wintypes.RECT(0, 0, largura, altura)
        user32.AdjustWindowRectEx.argtypes = [
            ctypes.POINTER(wintypes.RECT), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
        ]
        if user32.AdjustWindowRectEx(ctypes.byref(rect), estilo, False, estilo_ex):
            return rect.right - rect.left, rect.bottom - rect.top
    except Exception:  # noqa: BLE001
        pass
    return largura, altura + 40


def _fonte(gdi32, altura_px: int, peso: int = 400):
    try:
        return gdi32.CreateFontW(-int(altura_px), 0, 0, 0, peso, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI")
    except Exception:  # noqa: BLE001
        return None


def _criar(user32, hwnd, hinstance, classe, texto, estilo, r, id_controle=None):
    return user32.CreateWindowExW(
        0, classe, texto, estilo, r["x"], r["y"], r["largura"], r["altura"],
        hwnd, ctypes.c_void_p(id_controle) if id_controle else None, hinstance, None,
    )


def _barra_progresso(user32, hwnd, hinstance, r, timeout_ms: int):
    try:
        comctl32 = ctypes.windll.comctl32
        icc = _INITCOMMONCONTROLSEX(ctypes.sizeof(_INITCOMMONCONTROLSEX), _ICC_PROGRESS_CLASS)
        comctl32.InitCommonControlsEx(ctypes.byref(icc))
        barra = _criar(user32, hwnd, hinstance, "msctls_progress32", None, _WS_CHILD | _WS_VISIBLE, r)
        if barra:
            user32.SendMessageW(barra, PBM_SETRANGE32, 0, timeout_ms)
            user32.SendMessageW(barra, PBM_SETPOS, timeout_ms, 0)
        return barra or None
    except Exception:  # noqa: BLE001
        logger.debug("Barra de progresso do consentimento indisponível", exc_info=True)
        return None


def criar_controles(
    user32, hwnd, hinstance, timeout_seg: int, fontes=(), dpi: int = 96,
    id_sim: int = 1001, id_nao: int = 1002, id_contagem: int = 1003,
) -> dict:
    """Monta os controles; devolve handles para o WNDPROC e para a limpeza."""
    layout = layout_consentimento(dpi)
    gdi32 = ctypes.windll.gdi32
    gdi32.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
    gdi32.CreateFontW.restype = wintypes.HFONT
    f_titulo = _fonte(gdi32, layout["fontes"]["titulo"], 600)
    f_corpo = _fonte(gdi32, layout["fontes"]["corpo"])
    f_pequena = _fonte(gdi32, layout["fontes"]["pequena"])
    texto = _WS_CHILD | _WS_VISIBLE | _SS_LEFT | _SS_NOPREFIX
    botao = _WS_CHILD | _WS_VISIBLE | _WS_TABSTOP

    icone = carregar_icone(user32, layout["icone"]["largura"])
    if icone:
        h_icone = _criar(user32, hwnd, hinstance, "STATIC", None, _WS_CHILD | _WS_VISIBLE | _SS_ICON, layout["icone"])
        if h_icone:
            user32.SendMessageW(h_icone, STM_SETICON, icone, 0)
    itens = [
        (_criar(user32, hwnd, hinstance, "STATIC", TITULO_PERGUNTA, texto, layout["titulo"]), f_titulo),
        (_criar(user32, hwnd, hinstance, "STATIC", MENSAGEM, texto, layout["mensagem"]), f_corpo),
        (_criar(user32, hwnd, hinstance, "STATIC", descrever_fontes(fontes), texto, layout["fonte_detectada"]), f_corpo),
    ]
    hprog = _barra_progresso(user32, hwnd, hinstance, layout["progresso"], max(1, int(timeout_seg)) * 1000)
    hcount = _criar(user32, hwnd, hinstance, "STATIC", texto_contagem(timeout_seg), texto, layout["contagem"], id_contagem)
    sim = _criar(user32, hwnd, hinstance, "BUTTON", TEXTO_SIM, botao | _BS_DEFPUSHBUTTON, layout["botao_sim"], id_sim)
    nao = _criar(user32, hwnd, hinstance, "BUTTON", TEXTO_NAO, botao, layout["botao_nao"], id_nao)
    itens += [
        (hcount, f_pequena),
        (sim, f_corpo),
        (nao, f_corpo),
        (_criar(user32, hwnd, hinstance, "STATIC", DICA, texto, layout["dica"]), f_pequena),
    ]
    for handle, fonte in itens:
        if handle and fonte:
            user32.SendMessageW(handle, WM_SETFONT, fonte, 1)
    if sim:
        user32.SetFocus(sim)
    return {
        "hcount": hcount,
        "hprog": hprog,
        "hfonts": [f for f in (f_titulo, f_corpo, f_pequena) if f],
        "icone": icone,
        "layout": layout,
    }


def atualizar_contagem(user32, controles: dict, restante_ms: int) -> None:
    """Contagem decrescente: barra em ms e texto em segundos inteiros."""
    hprog = controles.get("hprog")
    if hprog:
        try:
            user32.SendMessageW(hprog, PBM_SETPOS, max(0, int(restante_ms)), 0)
        except Exception:  # noqa: BLE001
            pass
    hcount = controles.get("hcount")
    if hcount:
        try:
            user32.SetWindowTextW(hcount, texto_contagem((int(restante_ms) + 999) // 1000))
        except Exception:  # noqa: BLE001
            pass


def fundo_de_texto(user32, hdc) -> int:
    """WM_CTLCOLORSTATIC: STATIC e barra sobre o mesmo branco da janela (COLOR_WINDOW)."""
    try:
        gdi32 = ctypes.windll.gdi32
        gdi32.SetBkColor(ctypes.c_void_p(hdc), user32.GetSysColor(5))
        gdi32.SetTextColor(ctypes.c_void_p(hdc), user32.GetSysColor(8))  # COLOR_WINDOWTEXT
        return int(user32.GetSysColorBrush(5) or 0)
    except Exception:  # noqa: BLE001
        return 0


def liberar(controles: dict) -> None:
    try:
        gdi32 = ctypes.windll.gdi32
        for fonte in controles.get("hfonts", ()):
            gdi32.DeleteObject(fonte)
        if controles.get("icone"):
            ctypes.windll.user32.DestroyIcon(controles["icone"])
    except Exception:  # noqa: BLE001
        pass
