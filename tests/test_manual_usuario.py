# -*- coding: utf-8 -*-
"""Verificação estrutural do manual do usuário."""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MANUAL_MD = REPO / "docs" / "MANUAL-USUARIO.md"
MANUAL_PDF = REPO / "docs" / "MANUAL-USUARIO.pdf"

SECOES_OBRIGATORIAS = [
    "Instalação",
    "Bandeja",
    "Transcrição",
    "Diarização",
    "VOCÊ",
    "Meet",
    "Assistente",
    "Segurança",
    "Solução de problemas",
]


def _carregar_gerador():
    path = REPO / "scripts" / "gerar_manual_pdf.py"
    spec = importlib.util.spec_from_file_location("gerar_manual_pdf", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gerar_manual_pdf"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_manual_md_existe_e_tem_secoes():
    assert MANUAL_MD.is_file()
    texto = MANUAL_MD.read_text(encoding="utf-8")
    assert len(texto) > 5000
    for secao in SECOES_OBRIGATORIAS:
        assert secao.lower() in texto.lower(), f"Secao ausente: {secao}"


def test_manual_descreve_fluxo_seguro_da_v15():
    texto = MANUAL_MD.read_text(encoding="utf-8")
    minusculo = texto.lower()
    assert "transkriptor v1.5" in minusculo
    assert "processamento após a reunião" in minusculo
    assert "somente **sim**" in minusculo
    assert "antes de abrir" in minusculo
    assert ".txt" in minusculo and "arquivo principal" in minusculo
    assert "| transcrição manual |" not in minusculo
    assert "a gravação começa **antes** da pergunta" not in minusculo
    assert "trechos aparecem em notificação" not in minusculo


def test_gerar_pdf_produz_texto_legivel_na_pagina(tmp_path):
    """Regenera PDF via script real e valida texto extraível on-page."""
    mod = _carregar_gerador()
    destino = tmp_path / "manual_teste.pdf"
    mod.gerar_pdf(md_path=MANUAL_MD, pdf_path=destino)

    assert destino.stat().st_size > 10_240
    validacao = mod.validar_pdf_legivel(destino, min_chars=2500)
    assert validacao["ok"], (
        f"PDF ilegível: chars={validacao['chars']}, marcadores={validacao['marcadores']}"
    )

    texto = mod.extrair_texto_pdf(destino)
    for trecho in ("Transkriptor", "Google Meet", "Ollama", "127.0.0.1"):
        assert trecho.lower() in texto.lower(), f"Trecho ausente no PDF: {trecho}"


def test_manual_pdf_commitado_legivel():
    """PDF versionado no repo deve passar na mesma validação."""
    assert MANUAL_PDF.is_file(), "Execute: python scripts/gerar_manual_pdf.py"
    assert MANUAL_PDF.stat().st_size > 10_240
    assert MANUAL_PDF.read_bytes().startswith(b"%PDF")

    mod = _carregar_gerador()
    validacao = mod.validar_pdf_legivel(MANUAL_PDF, min_chars=2500)
    assert validacao["ok"], (
        f"docs/MANUAL-USUARIO.pdf ilegível — regenere com scripts/gerar_manual_pdf.py: "
        f"chars={validacao['chars']}"
    )
    texto = mod.extrair_texto_pdf(MANUAL_PDF).lower()
    assert "transkriptor v1.5" in texto
    assert "processamento após a reunião" in texto or "processamento apos a reuniao" in texto
