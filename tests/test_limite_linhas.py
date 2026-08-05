# -*- coding: utf-8 -*-
"""FR-8.2 / NFR-9.E2 — nenhum arquivo de produção passa de 500 linhas.

Era um gate manual do plano v1.3; virou teste na v1.4 porque duas refatorações
seguidas o estouraram sem ninguém perceber.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIMITE = 500

IGNORAR = {"conftest.py"}


def _arquivos_de_producao():
    for caminho in sorted(list(REPO.glob("*.py")) + list(REPO.glob("*.pyw"))):
        if caminho.name in IGNORAR:
            continue
        yield caminho


def test_nenhum_arquivo_de_producao_passa_de_500_linhas():
    excedentes = []
    for caminho in _arquivos_de_producao():
        linhas = len(caminho.read_text(encoding="utf-8").splitlines())
        if linhas > LIMITE:
            excedentes.append(f"{caminho.name}: {linhas} linhas")
    assert not excedentes, (
        "Arquivos acima do limite de 500 linhas (FR-8.2): " + "; ".join(excedentes)
    )
