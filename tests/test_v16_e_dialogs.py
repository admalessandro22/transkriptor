# -*- coding: utf-8 -*-
"""F11.E — diálogos Tk (T-11.E1/E2) → v1.9 (T-14.C3/D3): removidos; as tarefas vivem na Central."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FLOWS = (REPO / "transkriptor_menu_flows.py").read_text(encoding="utf-8")


def test_fluxos_nao_usam_tkinter():
    assert "tkinter" not in FLOWS and "simpledialog" not in FLOWS
    assert "_escolher_audio_dialog" not in FLOWS and "_renomear_dialog" not in FLOWS


def test_fluxos_abrem_a_central():
    assert "def abrir_central(" in FLOWS
    assert 'abrir_central(app, "diagnostico")' in FLOWS
    assert "def iniciar_retranscricao_ui" in FLOWS and "def rodar_diagnostico_ui" in FLOWS


def test_validacao_de_nome_vive_na_api():
    api = (REPO / "central_api.py").read_text(encoding="utf-8")
    assert "len(nome) < 2" in api
