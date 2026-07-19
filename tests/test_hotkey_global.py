# -*- coding: utf-8 -*-
"""T-F3 — atalho global Ctrl+Espaço (FR-3.*)."""
import threading
import time
from unittest.mock import MagicMock

import pytest

from hotkey_global import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_WIN,
    VK_SPACE,
    HotkeyGlobal,
    parse_atalho,
)


def test_parse_ctrl_space():
    assert parse_atalho("ctrl+space") == (MOD_CONTROL, VK_SPACE)


def test_parse_ctrl_shift_t():
    mods, vk = parse_atalho("ctrl+shift+t")
    assert mods == (MOD_CONTROL | MOD_SHIFT)
    assert vk == ord("T")


def test_parse_case_insensitive_spaces():
    assert parse_atalho("CTRL + SPACE") == (MOD_CONTROL, VK_SPACE)


def test_parse_invalidos():
    for bad in ("space", "ctrl+", "ctrl+enter+x", "", "ctrl+enter"):
        with pytest.raises(ValueError):
            parse_atalho(bad)


def test_hotkey_registro_ok_dispara_on_ativar():
    ativacoes = []
    falhas = []
    user32 = MagicMock()
    user32.RegisterHotKey.return_value = 1
    user32.UnregisterHotKey.return_value = 1
    msgs = []

    class MSG:
        def __init__(self, message=0, wParam=0):
            self.message = message
            self.wParam = wParam
            self.lParam = 0

    # GetMessageW: first WM_HOTKEY, then WM_QUIT
    def get_message(msg_ptr, *a):
        if not msgs:
            msgs.append("hotkey")
            # simulate writing to MSG - use side_effect via mock attributes
            return 1
        return 0  # WM_QUIT path: GetMessage returns 0

    # Better approach: control via list
    calls = {"n": 0}

    def gm(pMSG, hWnd, min, max):
        calls["n"] += 1
        if calls["n"] == 1:
            # fill message with WM_HOTKEY
            # pMSG is byref - we can't easily fill. Instead monkeypatch loop.
            return 1
        return 0

    user32.GetMessageW.side_effect = gm
    user32.PostThreadMessageW.return_value = 1

    # Unit-test the dispatch path directly + register/stop
    hk = HotkeyGlobal(
        "ctrl+space",
        on_ativar=lambda: ativacoes.append(1),
        on_falha=lambda m: falhas.append(m),
        user32=user32,
    )
    # inject fake message handling
    hk._poll_once = lambda: hk._despachar_hotkey() or False
    hk.start()
    time.sleep(0.15)
    hk.stop()
    time.sleep(0.05)

    assert user32.RegisterHotKey.called
    assert user32.UnregisterHotKey.call_count == 1
    assert ativacoes  # at least one from poll
    assert falhas == []


def test_hotkey_falha_registro_chama_on_falha():
    falhas = []
    user32 = MagicMock()
    user32.RegisterHotKey.return_value = 0
    hk = HotkeyGlobal(
        "ctrl+space",
        on_ativar=lambda: None,
        on_falha=lambda m: falhas.append(m),
        user32=user32,
    )
    hk.start()
    time.sleep(0.1)
    hk.stop()
    assert falhas
    assert hk.disponivel is False


def test_texto_menu_inclui_combo(modulo_transkriptor, monkeypatch):
    monkeypatch.setattr(modulo_transkriptor, "chave_disponivel", lambda: False)
    monkeypatch.setattr(modulo_transkriptor, "perfil_existe", lambda *a, **k: False)
    monkeypatch.setattr(modulo_transkriptor, "_carregar_config_user", lambda: {"atalho_global": "ctrl+space"})
    monkeypatch.setattr(modulo_transkriptor, "sincronizar_token_extensao", lambda *a, **k: None)
    # não registra hotkey real
    monkeypatch.setattr(
        modulo_transkriptor,
        "HotkeyGlobal",
        lambda *a, **k: MagicMock(disponivel=True, start=MagicMock(), stop=MagicMock()),
    )
    app = modulo_transkriptor.AppTranskriptor()
    texto = app._texto_transcricao_manual()
    assert "Ctrl" in texto or "ctrl" in texto.lower() or "Espaço" in texto or "Espaco" in texto
