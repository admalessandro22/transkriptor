# -*- coding: utf-8 -*-
"""Consentimento explícito e fail-closed antes da captura de reunião."""
from __future__ import annotations

import ctypes
import logging
import os
import threading
from ctypes import wintypes

from config import TIMEOUT_AVISO_GRAVACAO_SEG
from consentimento_controles import (
    ajustar_janela,
    ativar_dpi_na_thread,
    atualizar_contagem,
    carregar_icone,
    criar_controles,
    dpi_do_sistema,
    fundo_de_texto,
    liberar,
    restaurar_dpi_na_thread,
)
from consentimento_layout import layout_consentimento  # noqa: F401 (contrato UX-14.E3)
from transkriptor_acoes import IDNO, IDYES, MB_TIMEDOUT, resposta_autoriza_gravacao

logger = logging.getLogger(__name__)

TITULO_DIALOGO = "Transkriptor — confirmar gravação"
_ID_COUNTDOWN = 1003

_WM_CLOSE = 0x0010
_WM_DESTROY = 0x0002
_WM_COMMAND = 0x0111
_WM_TIMER = 0x0113
_WM_CTLCOLORSTATIC = 0x0138
_BN_CLICKED = 0
_ID_SIM = 1001
_ID_NAO = 1002
_ID_TIMER_CANCELAR = 1
_ID_TIMER_TIMEOUT = 2
_WS_EX_TOPMOST = 0x00000008
_WS_EX_TOOLWINDOW = 0x00000080
_WS_OVERLAPPED = 0x00000000
_WS_CAPTION = 0x00C00000
_WS_SYSMENU = 0x00080000
_WS_CHILD = 0x40000000
_WS_VISIBLE = 0x10000000
_WS_TABSTOP = 0x00010000
_BS_DEFPUSHBUTTON = 0x00000001
_SS_LEFT = 0x00000000
_SW_SHOW = 5
_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_SHOWWINDOW = 0x0040
_TIMER_INTERVAL_MS = 50
_UINT_PTR = ctypes.c_size_t

_LRESULT = ctypes.c_ssize_t
_WNDPROC = ctypes.WINFUNCTYPE(
    _LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


def _configurar_user32(user32):
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = _LRESULT
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL
    user32.SetTimer.argtypes = [wintypes.HWND, _UINT_PTR, wintypes.UINT, ctypes.c_void_p]
    user32.SetTimer.restype = _UINT_PTR
    user32.KillTimer.argtypes = [wintypes.HWND, _UINT_PTR]
    user32.KillTimer.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.SetFocus.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.UpdateWindow.argtypes = [wintypes.HWND]
    user32.UpdateWindow.restype = wintypes.BOOL
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    user32.UnregisterClassW.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.GetMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.TranslateMessage.restype = wintypes.BOOL
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.restype = _LRESULT
    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.PostQuitMessage.restype = None
    try:
        user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
        user32.SetWindowTextW.restype = wintypes.BOOL
    except Exception:
        pass
    try:
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SendMessageW.restype = wintypes.LPARAM
    except Exception:
        pass


def _criar_janela_consentimento(
    timeout_seg: int, resultado: dict, concluido, parar, fontes=(), dpi: int | None = None
) -> None:
    """Executa uma janela Win32 própria, sempre no topo, sem owner modal.

    UX-14.E3: a thread vira ciente de DPI (só ela), o layout é escalado por
    `layout_consentimento`, o ícone do produto vai na classe e a contagem tem
    barra de progresso. Cada um desses recursos, ao falhar, cai no anterior.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    _configurar_user32(user32)
    dpi_anterior = ativar_dpi_na_thread(user32)
    if dpi is None:
        dpi = dpi_do_sistema(user32)
    layout = layout_consentimento(dpi)
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
    hinstance = kernel32.GetModuleHandleW(None)
    classe = f"TranskriptorConsentimento_{os.getpid()}_{threading.get_ident()}"
    contexto = {"hwnd": None}

    def finalizar(valor: int) -> None:
        if concluido.is_set():
            return
        resultado["valor"] = valor
        concluido.set()
        hwnd = contexto.get("hwnd")
        if hwnd:
            user32.DestroyWindow(hwnd)

    import time as _time
    inicio = _time.monotonic()
    contexto["controles"] = {}
    timeout_ms = max(1, int(timeout_seg)) * 1000

    @_WNDPROC
    def proc(hwnd, mensagem, wparam, lparam):
        if mensagem == _WM_COMMAND:
            comando = int(wparam) & 0xFFFF
            notificacao = (int(wparam) >> 16) & 0xFFFF
            if notificacao == _BN_CLICKED and comando == _ID_SIM:
                finalizar(IDYES)
                return 0
            if notificacao == _BN_CLICKED and comando == _ID_NAO:
                finalizar(IDNO)
                return 0
        elif mensagem == _WM_CLOSE:
            finalizar(IDNO)
            return 0
        elif mensagem == _WM_TIMER:
            timer_id = int(wparam)
            if timer_id == _ID_TIMER_CANCELAR and parar.is_set():
                finalizar(MB_TIMEDOUT)
                return 0
            if timer_id == _ID_TIMER_TIMEOUT:
                finalizar(MB_TIMEDOUT)
                return 0
            if timer_id == _ID_TIMER_CANCELAR:
                restante_ms = max(0, timeout_ms - int((_time.monotonic() - inicio) * 1000))
                atualizar_contagem(user32, contexto["controles"], restante_ms)
                return 0
        elif mensagem == _WM_CTLCOLORSTATIC:
            # Só cor de fundo dos textos; não muda nenhuma porta de saída.
            pincel = fundo_de_texto(user32, wparam)
            if pincel:
                return pincel
        elif mensagem == _WM_DESTROY:
            user32.KillTimer(hwnd, _ID_TIMER_CANCELAR)
            user32.KillTimer(hwnd, _ID_TIMER_TIMEOUT)
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, mensagem, wparam, lparam)

    cursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))  # IDC_ARROW
    classe_registro = _WNDCLASSW(
        style=0,
        lpfnWndProc=proc,
        cbClsExtra=0,
        cbWndExtra=0,
        hInstance=hinstance,
        hIcon=carregar_icone(user32, layout["icone"]["largura"]),
        hCursor=cursor,
        hbrBackground=user32.GetSysColorBrush(5),  # COLOR_WINDOW
        lpszMenuName=None,
        lpszClassName=classe,
    )
    if not user32.RegisterClassW(ctypes.byref(classe_registro)):
        raise ctypes.WinError()
    try:
        estilo = _WS_OVERLAPPED | _WS_CAPTION | _WS_SYSMENU
        estilo_ex = _WS_EX_TOPMOST | _WS_EX_TOOLWINDOW
        largura, altura = ajustar_janela(
            user32, layout["janela"]["largura"], layout["janela"]["altura"], estilo, estilo_ex
        )
        x = max(0, (user32.GetSystemMetrics(0) - largura) // 2)
        y = max(0, (user32.GetSystemMetrics(1) - altura) // 2)
        hwnd = user32.CreateWindowExW(
            estilo_ex,
            classe,
            TITULO_DIALOGO,
            estilo,
            x,
            y,
            largura,
            altura,
            None,
            None,
            hinstance,
            None,
        )
        if not hwnd:
            raise ctypes.WinError()
        contexto["hwnd"] = hwnd
        contexto["controles"] = criar_controles(
            user32, hwnd, hinstance, timeout_seg, fontes, dpi, _ID_SIM, _ID_NAO, _ID_COUNTDOWN
        )
        user32.ShowWindow(hwnd, _SW_SHOW)
        user32.UpdateWindow(hwnd)
        user32.SetWindowPos(
            hwnd,
            _HWND_TOPMOST,
            0,
            0,
            0,
            0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW,
        )
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetTimer(hwnd, _ID_TIMER_CANCELAR, _TIMER_INTERVAL_MS, None)
        user32.SetTimer(hwnd, _ID_TIMER_TIMEOUT, max(1, int(timeout_seg)) * 1000, None)

        mensagem = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(mensagem), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(mensagem))
            user32.DispatchMessageW(ctypes.byref(mensagem))
    except Exception:
        logger.exception("Diálogo de consentimento indisponível; captura bloqueada")
        resultado["valor"] = 0
        concluido.set()
    finally:
        hwnd = contexto.get("hwnd")
        if hwnd:
            user32.KillTimer(hwnd, _ID_TIMER_CANCELAR)
            user32.KillTimer(hwnd, _ID_TIMER_TIMEOUT)
            if user32.IsWindow(hwnd):
                user32.DestroyWindow(hwnd)
        user32.UnregisterClassW(classe, hinstance)
        liberar(contexto.get("controles") or {})
        restaurar_dpi_na_thread(user32, dpi_anterior)
        if not concluido.is_set():
            resultado["valor"] = 0
            concluido.set()


def _mostrar_dialogo(timeout_seg: int, fontes=(), dpi: int | None = None) -> int:
    """Mostra uma confirmação sempre visível, mas não modal para o Windows."""
    resultado = {"valor": MB_TIMEDOUT}
    concluido = threading.Event()
    parar = threading.Event()
    janela = threading.Thread(
        target=_criar_janela_consentimento,
        args=(timeout_seg, resultado, concluido, parar, tuple(fontes or ()), dpi),
        daemon=True,
        name="Transkriptor-DialogoConsentimento",
    )
    janela.start()
    limite = max(1, int(timeout_seg)) + 2
    if not concluido.wait(limite):
        parar.set()
        janela.join(timeout=1)
        return MB_TIMEDOUT
    janela.join(timeout=1)
    return int(resultado["valor"])


def pedir_consentimento(timeout_seg: int = TIMEOUT_AVISO_GRAVACAO_SEG, fontes=()) -> bool:
    """Retorna True exclusivamente para a resposta Sim do diálogo.

    `fontes` são os nomes das fontes do detector (ex.: "titulo", "microfone");
    só viram rótulos fixos no diálogo, nunca título de janela nem nome.
    """
    try:
        # Sem fontes chama como na v1.8: dublês antigos aceitam um argumento só.
        extra = {"fontes": tuple(fontes)} if fontes else {}
        return resposta_autoriza_gravacao(_mostrar_dialogo(timeout_seg, **extra))
    except Exception:
        logger.exception("Diálogo de consentimento indisponível; captura bloqueada")
        return False
