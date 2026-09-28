# -*- coding: utf-8 -*-
"""Bandeja: hierarquia do menu (F11.D → v1.9 T-14.D2/E2).

O menu é lançador e indicador: ≤ 9 itens de topo, ≤ 2 níveis, estado por
`checked` nativo, todas as funções anteriores alcançáveis.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MENU = (REPO / "app_bandeja_menu.py").read_text(encoding="utf-8")
BLOCO = MENU[MENU.find("def _menu"):]


def test_menu_tem_no_maximo_nove_itens_de_topo():
    # Itens de topo = MenuItem com 8 espaços de indentação dentro de _menu (sem os separadores)
    topo = re.findall(r"^\s{12}pystray\.MenuItem\(", BLOCO, flags=re.MULTILINE)
    assert 1 <= len(topo) <= 9, f"{len(topo)} itens de topo"


def test_abrir_transkriptor_e_o_primeiro_item_acionavel():
    primeiro = re.search(r'pystray\.MenuItem\("([^"]+)", self\.', BLOCO)
    assert primeiro and primeiro.group(1) == "Abrir Transkriptor"
    assert "default=True" in BLOCO


def test_itens_com_estado_usam_checked():
    for nome in ("Gravação automática", "Separar vozes", "Identificar minha voz", "Identificar nomes do Meet", "Modo legendas Meet (Tactiq)", "Criar cópia criptografada (.tkpt)", "Iniciar com o Windows"):
        trecho = BLOCO[BLOCO.find(f'"{nome}"'):BLOCO.find(f'"{nome}"') + 200]
        assert "checked=lambda" in trecho, nome
    assert "✓ " not in BLOCO


def test_funcoes_legadas_continuam_alcancaveis():
    for item in [
        "Abrir pasta de transcrições", "Abrir assistente", "Retranscrever áudio", "Cadastrar minha voz",
        "Apagar perfil de voz", "Identificar nomes do Meet", "Renomear falante", "Criar cópia criptografada",
        "Modelo Whisper", "Iniciar com o Windows", "Abrir log", "Diagnóstico", "Sair",
    ]:
        assert item in BLOCO, f"Item legado ausente: {item}"
    assert BLOCO.count("pystray.Menu.SEPARATOR") >= 3


def test_menu_preserva_status_no_topo():
    assert "pystray.MenuItem(self._texto_status, None, enabled=False)" in BLOCO


def test_sem_prefixo_check_textual():
    assert "✓ " not in MENU
    for helper in ("_texto_deteccao", "_texto_diarizacao", "_texto_criptografia", "_texto_startup", "_texto_identificar_voz", "_texto_nomes_meet", "_texto_legendas_meet"):
        assert f"def {helper}" not in MENU, helper


def test_primeira_linha_usa_glossario():
    from types import SimpleNamespace

    from app_bandeja_menu import MenuBandejaMixin
    from app_estado_ui import ROTULOS

    class App(MenuBandejaMixin):
        transcritor = None
        deteccao_ativa = True
        _estado_processamento = None
        detector = SimpleNamespace(fontes_da_reuniao=[], instantaneo=lambda: [])

    app = App()
    assert app._texto_status().startswith(ROTULOS["aguardando"])
    app.deteccao_ativa = False
    assert app._texto_status().startswith(ROTULOS["pausado"])
    app.deteccao_ativa = True
    app._estado_processamento = "Em fila"
    assert app._texto_status().startswith(ROTULOS["processando"]) and "Em fila" in app._texto_status()
    app._estado_processamento = None
    app.transcritor = SimpleNamespace(rodando=True, diarizando=False)
    app.detector = SimpleNamespace(fontes_da_reuniao=["titulo"], instantaneo=lambda: [])
    assert app._texto_status() == f"{ROTULOS['gravando']} · titulo"
    app.transcritor = SimpleNamespace(rodando=False, diarizando=True)
    assert app._texto_status() == ROTULOS["separando_vozes"]
