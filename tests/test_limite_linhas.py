# -*- coding: utf-8 -*-
"""FR-8.2 / NFR-9.E2 — nenhum arquivo de produção passa de 500 linhas.

Era um gate manual do plano v1.3; virou teste na v1.4 porque duas refatorações
seguidas o estouraram sem ninguém perceber.
"""
import importlib.util
import sys
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


def _carregar_verificador_recursos():
    caminho = REPO / "scripts" / "verificar_recursos_gravacao.py"
    spec = importlib.util.spec_from_file_location("verificar_recursos_gravacao", caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_verificador_recursos_aplica_limites_da_v15():
    modulo = _carregar_verificador_recursos()

    aprovado = modulo.avaliar([200, 220], [1, 2], [1, 1])
    memoria = modulo.avaliar([100, 201], [1], [1])
    cpu = modulo.avaliar([100], [11], [1])
    icones = modulo.avaliar([100], [1], [1, 2])

    assert aprovado["ok"] is True
    assert memoria["ok"] is False
    assert cpu["ok"] is False
    assert icones["ok"] is False
    assert aprovado["limites"] == {
        "crescimento_memoria_mb": 100.0,
        "cpu_media_pct_um_nucleo": 10.0,
        "icones": 1,
    }


def test_gate_estatico_v15_inclui_recursos_e_fluxo():
    fonte = (REPO / "scripts" / "verificar_fase.py").read_text(encoding="utf-8")
    assert '"v1.5-estatico"' in fonte
    assert "test_fluxo_reuniao_v15.py" in fonte
    assert "test_limite_linhas.py" in fonte
