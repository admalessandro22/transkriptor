# -*- coding: utf-8 -*-
"""Fixtures compartilhadas do pytest."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolar_pasta_audio(monkeypatch, tmp_path):
    """Nenhum teste escreve na pasta de áudio real do usuário.

    Vários testes instanciam `Transcritor`, cujo `stop()` move o WAV para
    `PASTA_AUDIO`. Sem este isolamento, rodar a suíte sujava
    `transcricoes/audio/` com dezenas de arquivos de teste — indistinguíveis das
    gravações reais do usuário.
    """
    pasta = tmp_path / "audio_isolado"
    pasta.mkdir(exist_ok=True)
    for alvo in ("config.PASTA_AUDIO", "transcricao_core.PASTA_AUDIO"):
        try:
            monkeypatch.setattr(alvo, str(pasta))
        except (AttributeError, ImportError):
            pass
    return pasta


@pytest.fixture
def headers_token():
    from assistente import HEADER_TOKEN, obter_token_sessao

    return {HEADER_TOKEN: obter_token_sessao()}


@pytest.fixture
def chave_teste(monkeypatch, tmp_path):
    cfg = tmp_path / "config_user.json"
    chave_dpapi = tmp_path / "transkriptor_key.dpapi"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("config_user.CONFIG_USER_FILE", str(cfg))
    monkeypatch.setattr("config.ARQUIVO_CHAVE_DPAPI", str(chave_dpapi))
    monkeypatch.setattr("crypto_storage._dpapi_protect", lambda b: b"DPAPI:" + b)
    monkeypatch.setattr("crypto_storage._dpapi_unprotect", lambda b: b[6:])
    from crypto_storage import garantir_chave_mestra

    garantir_chave_mestra()
    return cfg


@pytest.fixture
def tmp_transcricoes(tmp_path):
    """Pasta isolada com um arquivo de transcrição de exemplo."""
    pasta = tmp_path / "transcricoes"
    pasta.mkdir()
    arquivo = pasta / "transcricao_2026-07-08_10h00.txt"
    arquivo.write_text(
        "=== Transcricao iniciada em 2026-07-08 10:00:00 ===\n\n"
        "[10:00:01] Ola equipe\n",
        encoding="utf-8",
    )
    return pasta


@pytest.fixture(scope="session")
def modulo_transkriptor():
    """Carrega o app .pyw sem executar o bloco __main__."""
    caminho = Path(__file__).resolve().parent.parent / "transkriptor.pyw"
    loader = SourceFileLoader("transkriptor_app_test", str(caminho))
    spec = spec_from_loader(loader.name, loader)
    modulo = module_from_spec(spec)
    loader.exec_module(modulo)
    return modulo
