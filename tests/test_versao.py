# -*- coding: utf-8 -*-
"""T-F1-02 — versão única do produto em config.VERSAO."""
import re
import tomllib
from pathlib import Path

import config

REPO = Path(__file__).resolve().parent.parent


def test_versao_config_bate_com_pyproject():
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert config.VERSAO == pyproject["project"]["version"]
    assert config.VERSAO == "1.7.0"


def test_transkriptor_pyw_sem_versao_hardcoded():
    src = (REPO / "transkriptor.pyw").read_text(encoding="utf-8")
    # Literais de versão semântica no pyw (exceto docstring genérica se usar VERSAO)
    padrao = re.compile(r"""['"]Transkriptor\s+\d+\.\d+""")
    assert not padrao.search(src), (
        "transkriptor.pyw não deve hardcodar versão; use config.VERSAO"
    )
    # Títulos da bandeja devem referenciar VERSAO
    assert "VERSAO" in src
    assert "from config import" in src or "import config" in src


def test_instalar_bat_le_versao_de_config():
    bat = (REPO / "instalar.bat").read_text(encoding="utf-8")
    assert "from config import VERSAO" in bat
    assert re.search(r"Instalando Transkriptor 1\.2\.\d", bat) is None


def test_agents_md_aponta_sdd_v15():
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert "docs/sdd/v1.6/" in agents
    # A fonte de verdade atual é a v1.6; a v1.5 agora é legado.
    assert "docs/sdd/v1.6/tasks.md" in agents


def test_v15_preserva_txt_principal_ao_criar_copia_criptografada():
    app = (REPO / "transkriptor.pyw").read_text(encoding="utf-8")
    menu = (REPO / "app_bandeja_menu.py").read_text(encoding="utf-8")
    assert "migrar_txt_legacy" not in app
    assert "migrar_txt_legacy" not in menu
