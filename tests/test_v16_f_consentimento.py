# -*- coding: utf-8 -*-
"""F11.F — Consentimento countdown + Segoe UI (T-11.F1)."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONS = (REPO / "consentimento_gravacao.py").read_text(encoding="utf-8")


def test_consentimento_tem_countdown():
    assert "_ID_COUNTDOWN" in CONS
    assert "1003" in CONS  # valor do ID
    assert "SetWindowTextW" in CONS
    assert "esta janela fecha automaticamente" in CONS.lower() or "fecha automaticamente" in CONS.lower()


def test_consentimento_tem_segoe_ui():
    assert "Segoe UI" in CONS
    assert "CreateFontW" in CONS
    assert "WM_SETFONT" in CONS or "0x0030" in CONS


def test_consentimento_janela_520x272():
    assert "520" in CONS
    assert "272" in CONS
    assert "largura, altura = 520, 272" in CONS


def test_consentimento_botoes_novo_tamanho():
    assert "224" in CONS  # Sim
    assert "132" in CONS  # Não
    assert "●" in CONS or "Sim, gravar" in CONS
    assert "Não gravar" in CONS


def test_consentimento_configura_user32():
    assert "SetWindowTextW" in CONS
    assert "SendMessageW" in CONS
    assert "_configurar_user32" in CONS


def test_consentimento_tem_hint_privacidade():
    assert "Nada é gravado antes do Sim" in CONS


def test_consentimento_nao_usa_messageboxtimeout():
    # Deve ter migrado de MessageBoxTimeoutW para janela própria
    assert "CreateWindowExW" in CONS
    assert "TOPMOST" in CONS
    assert "TOOLWINDOW" in CONS
