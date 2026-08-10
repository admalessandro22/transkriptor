# -*- coding: utf-8 -*-
"""A suíte não pode escrever no `transkriptor.log` do usuário.

Carregar `transkriptor.pyw` instala um RotatingFileHandler na raiz do logging.
Sem isolamento ele aponta para o log de produção, e a suíte injeta ali falhas
simuladas — "CUDA OOM simulado", "falha controlada", "CryptUnprotectData
falhou". Foi exatamente esse ruído que atrapalhou o diagnóstico do incidente de
2026-08-07: erros de teste e erros reais no mesmo arquivo, misturados por
timestamp.
"""
from __future__ import annotations

import logging
from pathlib import Path

import config


def _log_de_producao() -> Path:
    return (Path(__file__).resolve().parent.parent / "transkriptor.log").resolve()


def test_config_aponta_para_log_temporario(log_de_teste):
    assert Path(config.LOG_FILE).resolve() != _log_de_producao()
    assert Path(config.LOG_FILE).resolve() == Path(log_de_teste).resolve()


def test_nenhum_handler_escreve_no_log_de_producao(modulo_transkriptor):
    producao = _log_de_producao()

    destinos = [
        Path(h.baseFilename).resolve()
        for h in logging.root.handlers
        if hasattr(h, "baseFilename")
    ]

    assert destinos, "o app instala um handler de arquivo; nenhum foi encontrado"
    assert producao not in destinos, (
        f"a suíte está escrevendo no log de produção: {producao}"
    )


def test_log_de_producao_nao_e_tocado_pela_suite(modulo_transkriptor):
    """Prova direta: escrever agora não muda o arquivo do usuário."""
    producao = _log_de_producao()
    antes = producao.stat().st_mtime_ns if producao.exists() else None

    logging.getLogger(__name__).error("linha de teste que nunca deve vazar")

    depois = producao.stat().st_mtime_ns if producao.exists() else None
    assert depois == antes
