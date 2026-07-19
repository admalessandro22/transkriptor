# -*- coding: utf-8 -*-
"""Testes de manutenção Fase 6 — .gitignore e documentação."""
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def test_gitignore_existe():
    assert (REPO / ".gitignore").is_file()


@pytest.fixture
def git_repo(tmp_path):
    """Repo git temporário com .gitignore copiado da raiz do projeto."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    conteudo = (REPO / ".gitignore").read_text(encoding="utf-8")
    (tmp_path / ".gitignore").write_text(conteudo, encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "transcricoes").mkdir()
    (tmp_path / "_modelo_voz").mkdir(parents=True)
    (tmp_path / "_modelo_voz" / "perfil_usuario.npz").write_bytes(b"fake")
    (tmp_path / "_modelo_voz" / "perfil_usuario.enc").write_bytes(b"fake")
    (tmp_path / "_modelo_voz" / "vozes_conhecidas.json").write_text("{}", encoding="utf-8")
    (tmp_path / "_modelo_voz" / "vozes_conhecidas.enc").write_bytes(b"fake")
    (tmp_path / "transcricoes" / "reuniao.tkpt").write_bytes(b"fake")
    (tmp_path / "transcricoes" / "x.tkpt").write_bytes(b"fake")
    (tmp_path / "config_user.json").write_text("{}", encoding="utf-8")
    (tmp_path / "transkriptor.log").write_text("log", encoding="utf-8")
    (tmp_path / "terminals").mkdir()
    (tmp_path / "agent-tools").mkdir()
    (tmp_path / ".venv").mkdir()
    (tmp_path / "_a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "_srv.txt").write_text("x", encoding="utf-8")
    (tmp_path / "_srv2.txt").write_text("x", encoding="utf-8")
    return tmp_path


def test_git_check_ignore_caminhos_sensiveis(git_repo):
    caminhos = [
        "__pycache__",
        "transcricoes",
        "_modelo_voz/perfil_usuario.npz",
        "_modelo_voz/perfil_usuario.enc",
        "_modelo_voz/vozes_conhecidas.json",
        "_modelo_voz/vozes_conhecidas.enc",
        "transcricoes/reuniao.tkpt",
        "transcricoes/x.tkpt",
        "config_user.json",
        "transkriptor.log",
        "terminals",
        "agent-tools",
        "_a.txt",
        "_srv.txt",
        "_srv2.txt",
        ".venv",
    ]
    for rel in caminhos:
        r = subprocess.run(
            ["git", "check-ignore", "-v", rel],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"{rel} nao ignorado: {r.stderr}"


def test_verificacao_md_gates_f0_a_f8():
    path = REPO / "docs" / "VERIFICACAO.md"
    assert path.is_file()
    texto = path.read_text(encoding="utf-8")
    for fase in range(9):
        assert f"Fase {fase}" in texto or f"F{fase}" in texto
    assert "verificar_fase.py" in texto


def test_changelog_lista_fases_v12():
    path = REPO / "docs" / "sdd" / "v1.2" / "CHANGELOG.md"
    assert path.is_file()
    texto = path.read_text(encoding="utf-8")
    for label in (
        "Fase 0", "Fase 1", "Fase 2", "Fase 3", "Fase 4",
        "Fase 5", "Fase 6", "Fase 7", "Fase 8",
    ):
        assert label in texto


def test_gate_estabilidade_lista_testes_do_hotfix():
    texto = (REPO / "scripts" / "verificar_fase.py").read_text(encoding="utf-8")
    assert '"estabilidade"' in texto
    assert "tests/test_bandeja_lifecycle.py" in texto
    assert "tests/test_integracao_monitor_meet.py" in texto
    assert "tests/test_atalho_desktop.py" in texto
