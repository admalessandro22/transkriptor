# -*- coding: utf-8 -*-
"""Regressão 2026-09-29 — o .txt provisório da captura bloqueava o worker.

No modo só-áudio (como o app grava reuniões), o Transcritor abria um .txt de
cabeçalho com o mesmo nome-base do job; desde 863261d o worker recusa gravar
sobre resultado existente ("revisão manual preservada") e a reunião terminava
sem transcrição. O gate de 25 s reprovou assim em 29/09/2026.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from transcricao_core import Transcritor


@pytest.fixture(autouse=True)
def _modo_compativel(monkeypatch):
    """O bug só existe sem proteção: é o modo do usuário que reprovou o gate."""
    from politica_privacidade import ProtectionMode

    for alvo in ("politica_privacidade.modo_efetivo", "transcricao_core.modo_efetivo"):
        monkeypatch.setattr(alvo, lambda: ProtectionMode.COMPATIBLE)
    monkeypatch.setattr("crypto_storage.chave_disponivel", lambda: False)


def _abrir(tmp_path, *, ao_vivo):
    t = Transcritor(pasta_saida=str(tmp_path), capturar_mic=False, criptografar=False,
                    processar_ao_vivo=ao_vivo)
    t._abrir_arquivo()
    return t


def test_somente_audio_nao_cria_txt_provisorio(tmp_path):
    t = _abrir(tmp_path, ao_vivo=False)
    try:
        assert t._caminho_saida.endswith(".txt")
        assert not Path(t._caminho_saida).exists()
        assert Path(t._caminho_wav).exists()
    finally:
        t._finalizar_arquivo_texto()
        t._wav.close()
    assert not Path(t._caminho_saida).exists()


def test_ao_vivo_continua_escrevendo_txt(tmp_path):
    t = _abrir(tmp_path, ao_vivo=True)
    try:
        assert Path(t._caminho_saida).exists()
    finally:
        t._finalizar_arquivo_texto()
        t._wav.close()
    assert "Encerrado em" in Path(t._caminho_saida).read_text(encoding="utf-8")


def test_worker_nao_encontra_resultado_previo_da_captura(tmp_path):
    """O nome-base do job é o da captura; nada com esse nome pode existir antes."""
    t = _abrir(tmp_path, ao_vivo=False)
    try:
        base = Path(t._caminho_saida).stem
        assert not (tmp_path / f"{base}.txt").exists()
        assert not (tmp_path / f"{base}.tkpt").exists()
    finally:
        t._finalizar_arquivo_texto()
        t._wav.close()


def test_somente_audio_protegido_nao_sela_cabecalho(chave_teste, tmp_path, monkeypatch):
    """No modo protegido o cabeçalho virava .tkpt no stop e colidia igual."""
    from politica_privacidade import ProtectionMode

    for alvo in ("politica_privacidade.modo_efetivo", "transcricao_core.modo_efetivo"):
        monkeypatch.setattr(alvo, lambda: ProtectionMode.PROTECTED)
    t = Transcritor(pasta_saida=str(tmp_path), capturar_mic=False, processar_ao_vivo=False)
    t._abrir_arquivo()
    caminho = Path(t._caminho_saida)
    t._finalizar_arquivo_texto()
    t._wav.close()
    assert caminho.suffix == ".tkpt"
    assert not caminho.exists()
