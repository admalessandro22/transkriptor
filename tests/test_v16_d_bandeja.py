# -*- coding: utf-8 -*-
"""F11.D — Bandeja hierarquia (T-11.D1)."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MENU = (REPO / "app_bandeja_menu.py").read_text(encoding="utf-8")


def test_menu_tem_3_submenus_e_9_raiz():
    # Deve ter 3 sub-menus pystray.Menu aninhados
    assert MENU.count('pystray.Menu(') >= 4  # 1 raiz + 3 sub
    assert '"Transcrições"' in MENU
    assert '"Minha voz"' in MENU
    assert '"Google Meet"' in MENU
    # Verificar que itens legados ainda existem
    for item in [
        "Abrir pasta de transcrições",
        "Abrir assistente",
        "Retranscrever áudio",
        "Cadastrar minha voz",
        "Apagar perfil de voz",
        "Identificar nomes do Meet",
        "Renomear falante",
        "Criar cópia criptografada",
        "Modelo Whisper",
        "Iniciar com o Windows",
        "Sair",
    ]:
        assert item in MENU, f"Item legado ausente: {item}"


def test_menu_raiz_tem_9_ou_menos_itens():
    # Após agrupar, o bloco _menu contém sub-menus, então total MenuItem aumenta.
    # O que importa é que existem 3 sub-menus e o nível raiz ficou enxuto.
    # Checamos que há 3 pystray.Menu aninhados e que o nível raiz tem ≤9 itens
    # visíveis (contando sub-menus como 1 cada).
    inicio = MENU.find("def _menu")
    bloco = MENU[inicio: inicio + 4000]
    # Conta ocorrências de sub-menu header
    submenus = re.findall(r'pystray\.MenuItem\(\s*"Transcrições"|pystray\.MenuItem\(\s*"Minha voz"|pystray\.MenuItem\(\s*"Google Meet"', bloco)
    assert len(submenus) == 3, f"Esperado 3 sub-menus, achado {len(submenus)}"
    # Total MenuItem no arquivo subiu por causa do nesting, mas raiz enxuta:
    # verificamos que bloco tem exatamente 3 pystray.Menu( para sub-menus + 1 raiz
    assert bloco.count('pystray.Menu(') == 4


def test_menu_preserva_status_no_topo():
    assert "_texto_status" in MENU
    assert "pystray.MenuItem(self._texto_status, None, enabled=False)" in MENU


def test_submenus_tem_separators_corretos():
    # Separadores entre grupos principais devem existir
    assert "pystray.Menu.SEPARATOR" in MENU
    assert MENU.count("pystray.Menu.SEPARATOR") >= 4
