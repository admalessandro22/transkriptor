# -*- coding: utf-8 -*-
"""F11.E — Diálogos premium (T-11.E1/E2)."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FLOWS = (REPO / "transkriptor_menu_flows.py").read_text(encoding="utf-8")


def test_dialog_retranscrever_listbox():
    # T-11.E1: _escolher_audio_dialog deve existir e usar Listbox
    assert "_escolher_audio_dialog" in FLOWS
    assert "Listbox" in FLOWS
    assert "Scrollbar" in FLOWS
    assert "560x420" in FLOWS or "560" in FLOWS
    assert "Double-Button-1" in FLOWS
    assert "filtrar" in FLOWS.lower() or "search_var" in FLOWS
    # Fallback simpledialog preservado
    assert "simpledialog.askstring" in FLOWS
    # Confirma que iniciar_retranscricao_ui chama o dialog premium
    assert "iniciar_retranscricao_ui" in FLOWS
    assert "_escolher_audio_dialog" in FLOWS[FLOWS.find("def iniciar_retranscricao_ui"):FLOWS.find("def iniciar_retranscricao_ui")+3000]


def test_dialog_renomear_combobox():
    # T-11.E2
    assert "_renomear_dialog" in FLOWS
    assert "Combobox" in FLOWS
    assert "readonly" in FLOWS
    assert "420x220" in FLOWS or "420" in FLOWS
    assert "erro_var" in FLOWS or "Nome muito curto" in FLOWS
    assert "FALANTE_XX" in FLOWS or "FALANTE" in FLOWS
    # Validação <2
    assert 'len(nome) < 2' in FLOWS


def test_dialogs_sao_topmost_e_grab():
    assert 'attributes("-topmost"' in FLOWS
    assert "grab_set" in FLOWS
    assert 'transient(root)' in FLOWS


def test_dialogs_tem_fallback():
    # Ambos devem ter try/except fallback para simpledialog
    assert FLOWS.count("simpledialog") >= 2


def test_retranscrever_nao_usa_escolha_numerica_direta():
    # O fluxo novo não deve mais usar opcoes = "\n".join diretamente como prompt principal
    # Mas pode existir no fallback, então checamos que Listbox é o caminho principal
    idx = FLOWS.find("def _escolher_audio_dialog")
    assert idx != -1
    bloco = FLOWS[idx: idx + 2000]
    assert "Listbox" in bloco
