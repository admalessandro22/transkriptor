# -*- coding: utf-8 -*-
"""Hotkey global Win32 via RegisterHotKey (FR-3.*)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes  # necessário: `import ctypes` sozinho não expõe o submódulo
import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_SPACE = 0x20
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
HOTKEY_ID = 0x544B  # 'TK'


def parse_atalho(texto: str) -> tuple[int, int]:
    """Converte 'ctrl+space' → (modificadores, vk). Case-insensitive, separador +."""
    if not texto or not str(texto).strip():
        raise ValueError("atalho vazio")
    partes = [p.strip().lower() for p in str(texto).split("+") if p.strip()]
    if len(partes) < 2:
        raise ValueError(f"atalho inválido: {texto!r}")
    mods = 0
    tecla = None
    for p in partes:
        if p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p == "alt":
            mods |= MOD_ALT
        elif p == "shift":
            mods |= MOD_SHIFT
        elif p in ("win", "windows", "super"):
            mods |= MOD_WIN
        elif tecla is None:
            tecla = p
        else:
            raise ValueError(f"atalho inválido: {texto!r}")
    if tecla is None or mods == 0:
        raise ValueError(f"atalho inválido: {texto!r}")
    if tecla in ("space", "espaço", "espaco"):
        vk = VK_SPACE
    elif len(tecla) == 1 and tecla.isalpha():
        vk = ord(tecla.upper())
    elif len(tecla) == 1 and tecla.isdigit():
        vk = ord(tecla)
    elif tecla.startswith("f") and tecla[1:].isdigit():
        n = int(tecla[1:])
        if not 1 <= n <= 12:
            raise ValueError(f"atalho inválido: {texto!r}")
        vk = 0x70 + (n - 1)  # VK_F1
    else:
        raise ValueError(f"atalho inválido: {texto!r}")
    return mods, vk


def formatar_atalho(texto: str) -> str:
    """'ctrl+space' → 'Ctrl+Espaço' para UI."""
    partes = [p.strip().lower() for p in str(texto).split("+") if p.strip()]
    out = []
    for p in partes:
        if p in ("ctrl", "control"):
            out.append("Ctrl")
        elif p == "alt":
            out.append("Alt")
        elif p == "shift":
            out.append("Shift")
        elif p in ("win", "windows", "super"):
            out.append("Win")
        elif p in ("space", "espaço", "espaco"):
            out.append("Espaço")
        else:
            out.append(p.upper() if len(p) == 1 else p.capitalize())
    return "+".join(out)


def _user32_default():
    return ctypes.windll.user32


class HotkeyGlobal:
    """Registra hotkey em thread daemon com message loop."""

    def __init__(
        self,
        combo_texto: str,
        on_ativar: Callable[[], None],
        on_falha: Callable[[str], None] | None = None,
        user32=None,
        hotkey_id: int = HOTKEY_ID,
    ):
        self.combo_texto = combo_texto
        self.on_ativar = on_ativar
        self.on_falha = on_falha or (lambda _m: None)
        self._user32 = user32
        self._hotkey_id = hotkey_id
        self.disponivel = False
        self._thread: threading.Thread | None = None
        self._tid = None
        self._stop = threading.Event()
        self._mods, self._vk = parse_atalho(combo_texto)

    def _api(self):
        return self._user32 if self._user32 is not None else _user32_default()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="HotkeyGlobal")
        self._thread.start()

    def stop(self):
        # UnregisterHotKey só funciona na thread que registrou; quem desregistra
        # é o próprio loop ao sair (WM_QUIT). Se o join expirar, o Windows limpa
        # o registro no encerramento do processo.
        self._stop.set()
        tid = self._tid
        if tid:
            try:
                self._api().PostThreadMessageW(tid, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2)

    def _despachar_hotkey(self):
        def _run():
            try:
                self.on_ativar()
            except Exception:
                logger.exception("on_ativar do hotkey falhou")

        threading.Thread(target=_run, daemon=True).start()

    def _loop(self):
        api = self._api()
        self._tid = threading.get_ident()
        ok = api.RegisterHotKey(None, self._hotkey_id, self._mods, self._vk)
        if not ok:
            self.disponivel = False
            try:
                self.on_falha(f"Atalho {self.combo_texto} indisponível")
            except Exception:
                logger.exception("on_falha")
            return
        self.disponivel = True
        # message loop
        if hasattr(self, "_poll_once"):
            # modo teste: poll até stop
            while not self._stop.is_set():
                cont = self._poll_once()
                if cont is False:
                    break
                time_sleep_brief()
            try:
                api.UnregisterHotKey(None, self._hotkey_id)
            except Exception:
                pass
            self.disponivel = False
            return

        msg = ctypes.wintypes.MSG()
        while not self._stop.is_set():
            # GetMessageW blocks; 0 = WM_QUIT, -1 = error
            r = api.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r == 0 or r == -1:
                break
            if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                self._despachar_hotkey()
        try:
            api.UnregisterHotKey(None, self._hotkey_id)
        except Exception:
            pass
        self.disponivel = False


def time_sleep_brief():
    import time

    time.sleep(0.05)
