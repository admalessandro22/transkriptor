# -*- coding: utf-8 -*-
"""NFR-10.H4 — um dublê que mente esconde o defeito que ele deveria pegar.

Em 2026-08-07 o app travou em toda reunião e 380 testes passavam. O motivo:
todos os dublês de `Transcritor` tinham `start()` que só fazia
`self.rodando = True`. O `Transcritor` de verdade chama `on_status` de dentro do
`start()` — e era essa chamada que fechava o deadlock com `self._lock`.

Este teste lê a suíte e exige que todo dublê de `Transcritor` reproduza o
contrato observável do original: `start()` e `stop()` reportam status.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

DIR_TESTES = Path(__file__).resolve().parent
RAIZ = DIR_TESTES.parent

# Métodos do Transcritor real que chamam `on_status` incondicionalmente.
METODOS_QUE_REPORTAM = ("start", "stop")


def _classes_dubles():
    """Toda classe de teste que se faz passar por um Transcritor."""
    for arquivo in sorted(DIR_TESTES.glob("test_*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=arquivo.name)
        for no in ast.walk(arvore):
            if not isinstance(no, ast.ClassDef):
                continue
            if "transcritor" not in no.name.lower():
                continue
            metodos = {
                m.name: m
                for m in no.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if "start" in metodos:
                yield arquivo.name, no.name, metodos


def _reporta_status(metodo: ast.FunctionDef) -> bool:
    for no in ast.walk(metodo):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            if no.func.attr == "on_status":
                return True
    return False


def test_existe_algum_duble_de_transcritor():
    """Guarda contra o teste virar vácuo se os dublês mudarem de nome."""
    assert list(_classes_dubles()), "nenhum dublê de Transcritor encontrado"


def test_transcritor_real_reporta_status_no_start_e_no_stop():
    """A premissa do guarda: é isto que os dublês têm de imitar."""
    fonte = (RAIZ / "transcricao_core.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    classe = next(
        n for n in ast.walk(arvore)
        if isinstance(n, ast.ClassDef) and n.name == "Transcritor"
    )
    metodos = {m.name: m for m in classe.body if isinstance(m, ast.FunctionDef)}

    for nome in METODOS_QUE_REPORTAM:
        assert _reporta_status(metodos[nome]), (
            f"Transcritor.{nome} não chama mais on_status — reveja este guarda"
        )


@pytest.mark.parametrize(
    "arquivo,classe,metodos",
    [pytest.param(a, c, m, id=f"{a}::{c}") for a, c, m in _classes_dubles()],
)
def test_duble_de_transcritor_reporta_status(arquivo, classe, metodos):
    faltando = [
        nome
        for nome in METODOS_QUE_REPORTAM
        if nome in metodos and not _reporta_status(metodos[nome])
    ]

    assert not faltando, (
        f"{arquivo}::{classe}.{'/'.join(faltando)} não chama on_status. "
        "O Transcritor real chama — um dublê mudo não exercita o caminho que "
        "travou o app em 2026-08-07."
    )
