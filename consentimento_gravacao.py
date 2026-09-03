# -*- coding: utf-8 -*-
"""Consentimento explícito e fail-closed antes da captura de reunião."""
from __future__ import annotations

import ctypes
import logging
import os
import threading
from ctypes import wintypes

from config import TIMEOUT_AVISO_GRAVACAO_SEG
from transkriptor_acoes import IDNO, IDYES, MB_TIMEDOUT, resposta_autoriza_gravacao

logger = logging.getLogger(__name__)

TITULO_DIALOGO = "Transkriptor — confirmar gravação"
_MENSAGEM_DIALOGO = (
    "O Transkriptor detectou uma reunião.\r\n\r\n"
    "Quer gravar o áudio e gerar a transcrição em texto?\r\n\r\n"
    "A captura só começa depois de escolher Sim.\r\n"
    "Não ou ausência de resposta não gravam esta reunião."
)
_ID_COUNTDOWN = 1003

_WM_CLOSE = 0x0010
_WM_DESTROY = 0x0002
_WM_COMMAND = 0x0111
_WM_TIMER = 0x0113
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


def _criar_controles(user32, hwnd, hinstance, timeout_seg: int = 30):
    from ctypes import wintypes as _wt
    # Tipografia Segoe UI para o diálogo (melhor legibilidade em HiDPI)
    try:
        gdi32 = ctypes.windll.gdi32
        gdi32.CreateFontW.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR,
        ]
        gdi32.CreateFontW.restype = wintypes.HFONT
        hfont = gdi32.CreateFontW(-15, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI")
        hfont_small = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI")
    except Exception:
        hfont = None
        hfont_small = None

    estilo_texto = _WS_CHILD | _WS_VISIBLE | _SS_LEFT
    estilo_botao = _WS_CHILD | _WS_VISIBLE | _WS_TABSTOP
    # Mensagem principal — janela maior para respiro
    hstatic = user32.CreateWindowExW(
        0,
        "STATIC",
        _MENSAGEM_DIALOGO,
        estilo_texto,
        22,
        18,
        472,
        118,
        hwnd,
        None,
        hinstance,
        None,
    )
    # Countdown — atualização a cada segundo
    hcount = user32.CreateWindowExW(
        0,
        "STATIC",
        f"Esta janela fecha automaticamente em {int(timeout_seg)}s (Não gravar).",
        estilo_texto | 0x00000002,  # SS_CENTERIMAGE-like align left with muted hint
        22,
        138,
        472,
        18,
        hwnd,
        ctypes.c_void_p(_ID_COUNTDOWN),
        hinstance,
        None,
    )
    if hfont and hstatic:
        user32.SendMessageW(hstatic, 0x0030, hfont, 1)  # WM_SETFONT
    if hfont_small and hcount:
        user32.SendMessageW(hcount, 0x0030, hfont_small, 1)
    # Botões — Sim primário maior, Não secundário
    sim = user32.CreateWindowExW(
        0,
        "BUTTON",
        "●  Sim, gravar reunião",
        estilo_botao | _BS_DEFPUSHBUTTON,
        22,
        166,
        224,
        36,
        hwnd,
        ctypes.c_void_p(_ID_SIM),
        hinstance,
        None,
    )
    nao = user32.CreateWindowExW(
        0,
        "BUTTON",
        "Não gravar",
        estilo_botao,
        258,
        166,
        132,
        36,
        hwnd,
        ctypes.c_void_p(_ID_NAO),
        hinstance,
        None,
    )
    if hfont and sim:
        user32.SendMessageW(sim, 0x0030, hfont, 1)
    if hfont and nao:
        user32.SendMessageW(nao, 0x0030, hfont, 1)
    # Dica de privacidade
    hhint = user32.CreateWindowExW(
        0,
        "STATIC",
        "Nada é gravado antes do Sim. O áudio fica local em transcrições/audio.",
        estilo_texto,
        22,
        210,
        472,
        16,
        hwnd,
        None,
        hinstance,
        None,
    )
    if hfont_small and hhint:
        user32.SendMessageW(hhint, 0x0030, hfont_small, 1)
    if sim:
        user32.SetFocus(sim)
    return hcount


def _criar_janela_consentimento(timeout_seg: int, resultado: dict, concluido, parar) -> None:
    """Executa uma janela Win32 própria, sempre no topo, sem owner modal."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    _configurar_user32(user32)
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
    contexto["hcount"] = None

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
                # Atualizar countdown a cada ~50ms, mas só mudar texto quando o segundo virar
                hcount = contexto.get("hcount")
                if hcount:
                    restante = max(0, int(timeout_seg) - int(_time.monotonic() - inicio))
                    try:
                        txt = f"Esta janela fecha automaticamente em {restante}s (Não gravar)."
                        user32.SetWindowTextW(hcount, txt)
                    except Exception:
                        pass
                return 0
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
        hIcon=None,
        hCursor=cursor,
        hbrBackground=user32.GetSysColorBrush(5),  # COLOR_WINDOW
        lpszMenuName=None,
        lpszClassName=classe,
    )
    if not user32.RegisterClassW(ctypes.byref(classe_registro)):
        raise ctypes.WinError()
    try:
        largura, altura = 520, 272
        x = max(0, (user32.GetSystemMetrics(0) - largura) // 2)
        y = max(0, (user32.GetSystemMetrics(1) - altura) // 2)
        hwnd = user32.CreateWindowExW(
            _WS_EX_TOPMOST | _WS_EX_TOOLWINDOW,
            classe,
            TITULO_DIALOGO,
            _WS_OVERLAPPED | _WS_CAPTION | _WS_SYSMENU,
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
        contexto["hcount"] = _criar_controles(user32, hwnd, hinstance, timeout_seg)
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
        if not concluido.is_set():
            resultado["valor"] = 0
            concluido.set()


def _mostrar_dialogo(timeout_seg: int) -> int:
    """Mostra uma confirmação sempre visível, mas não modal para o Windows."""
    resultado = {"valor": MB_TIMEDOUT}
    concluido = threading.Event()
    parar = threading.Event()
    janela = threading.Thread(
        target=_criar_janela_consentimento,
        args=(timeout_seg, resultado, concluido, parar),
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


def pedir_consentimento(timeout_seg: int = TIMEOUT_AVISO_GRAVACAO_SEG) -> bool:
    """Retorna True exclusivamente para a resposta Sim do diálogo."""
    try:
        return resposta_autoriza_gravacao(_mostrar_dialogo(timeout_seg))
    except Exception:
        logger.exception("Diálogo de consentimento indisponível; captura bloqueada")
        return False
