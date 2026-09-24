"""T-13.A1 — rastreabilidade da especificação SDD ativa.

Estes testes exercitam somente arquivos de governança e o verificador de fase;
não importam a bandeja nem inicializam recursos de produção.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SDD_ATIVO = REPO / "docs" / "sdd" / "v1.8"
VERIFICADOR = REPO / "scripts" / "verificar_fase.py"


def test_remediacao_reabre_tarefas_incompletas():
    tasks = (SDD_ATIVO / "tasks.md").read_text(encoding="utf-8")
    for tarefa in ("D1", "D2", "D4", "D5", "D6", "D7", "E1", "E4", "F3", "G1", "G2"):
        linha = next(
            linha for linha in tasks.splitlines()
            if f"T-13.{tarefa}" in linha and "Requisito" in linha
        )
        assert "REOPENED" in linha or "BLOCKED" in linha
    assert "23 DONE" not in tasks


def _verificar(
    sdd_root: Path, *, tarefa: str | None = None
) -> subprocess.CompletedProcess[str]:
    comando = [
        sys.executable,
        str(VERIFICADOR),
        "--fase",
        "v1.8-sdd",
        "--sdd-root",
        str(sdd_root),
    ]
    if tarefa is not None:
        comando.extend(["--tarefa", tarefa])
    return subprocess.run(
        comando,
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_referencia_ativa_nao_aponta_tasks_legadas():
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    indice = (REPO / "docs" / "sdd" / "README.md").read_text(encoding="utf-8")

    for caminho in (
        "docs/sdd/v1.8/plan.md",
        "docs/sdd/v1.8/concept.md",
        "docs/sdd/v1.8/spec.md",
        "docs/sdd/v1.8/tasks.md",
    ):
        assert caminho in agents
    assert "Executar uma tarefa por vez de `docs/sdd/v1.5/tasks.md`." not in agents
    assert "[v1.8](v1.8/README.md)" in indice


def test_requisito_sem_task_reprova(tmp_path: Path):
    copia = tmp_path / "v1.8"
    shutil.copytree(SDD_ATIVO, copia)
    spec = copia / "spec.md"
    spec.write_text(
        spec.read_text(encoding="utf-8")
        + "\n| FR-13.Z9 | requisito injetado sem tarefa | T-13.Z9 |\n",
        encoding="utf-8",
    )

    resultado = _verificar(copia)

    assert resultado.returncode == 1
    assert "RASTREABILIDADE FALHOU" in resultado.stderr
    assert "requisito sem task: FR-13.Z9 -> T-13.Z9" in resultado.stderr


def test_indice_referencia_decisoes_confirmadas():
    resultado = _verificar(SDD_ATIVO)

    assert resultado.returncode == 0, resultado.stderr
    assert "RASTREABILIDADE OK" in resultado.stdout


def test_tarefa_executada_reprova_seletor_ausente(tmp_path: Path):
    copia = tmp_path / "v1.8"
    shutil.copytree(SDD_ATIVO, copia)
    tasks = copia / "tasks.md"
    tasks.write_text(
        tasks.read_text(encoding="utf-8").replace(
            "tests/test_sdd_rastreabilidade.py", "tests/test_seletor_ausente.py"
        ),
        encoding="utf-8",
    )

    resultado = _verificar(copia, tarefa="T-13.A1")

    assert resultado.returncode == 1
    assert "seletor ausente para T-13.A1: tests/test_seletor_ausente.py" in resultado.stderr
