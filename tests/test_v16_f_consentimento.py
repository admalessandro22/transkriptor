# -*- coding: utf-8 -*-
"""F11.F — Consentimento countdown + Segoe UI (T-11.F1).

Migrado na v1.9 (T-14.E3): a geometria vive em `consentimento_layout` (escalada
por DPI, base 520 px) e os controles Win32 em `consentimento_controles`;
`consentimento_gravacao.py` mantém IDs, timers e o `WNDPROC`.
"""
from pathlib import Path

from consentimento_layout import DICA, TEXTO_NAO, TEXTO_SIM, layout_consentimento, texto_contagem

REPO = Path(__file__).resolve().parent.parent
CONS = (REPO / "consentimento_gravacao.py").read_text(encoding="utf-8")
CONTROLES = (REPO / "consentimento_controles.py").read_text(encoding="utf-8")


def test_consentimento_tem_countdown():
    assert "_ID_COUNTDOWN" in CONS
    assert "1003" in CONS  # valor do ID
    assert "SetWindowTextW" in CONTROLES
    assert "sem gravar" in texto_contagem(30).lower()


def test_consentimento_tem_segoe_ui():
    assert "Segoe UI" in CONTROLES
    assert "CreateFontW" in CONTROLES
    assert "WM_SETFONT" in CONTROLES


def test_consentimento_janela_base_520():
    base = layout_consentimento(96)
    assert base["janela"]["largura"] == 520
    assert base["janela"]["altura"] >= 272


def test_consentimento_botoes_novo_tamanho():
    base = layout_consentimento(96)
    assert base["botao_sim"]["largura"] >= 224  # Sim
    assert base["botao_nao"]["largura"] >= 132  # Não
    assert TEXTO_SIM == "Gravar esta reunião"
    assert TEXTO_NAO == "Não gravar"


def test_consentimento_configura_user32():
    assert "SetWindowTextW" in CONS
    assert "SendMessageW" in CONS
    assert "_configurar_user32" in CONS


def test_consentimento_tem_hint_privacidade():
    assert DICA.startswith("Nada é gravado antes")


def test_consentimento_nao_usa_messageboxtimeout():
    # Deve ter migrado de MessageBoxTimeoutW para janela própria
    assert "CreateWindowExW" in CONS
    assert "TOPMOST" in CONS
    assert "TOOLWINDOW" in CONS
