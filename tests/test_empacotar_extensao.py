# -*- coding: utf-8 -*-
"""T-15.E5 / FR-15.E5 — pacote da extensão para a Chrome Web Store / Edge Add-ons."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

import config
from scripts.empacotar_extensao import empacotar

RAIZ = Path(__file__).resolve().parent.parent


def _zip(tmp_path, nome="ext.zip"):
    destino = tmp_path / nome
    empacotar(destino)
    return destino


def test_zip_sem_key_nem_arquivos_de_desenvolvimento(tmp_path):
    with zipfile.ZipFile(_zip(tmp_path)) as z:
        nomes = set(z.namelist())
        manifesto = json.loads(z.read("manifest.json"))
    assert "key" not in manifesto  # a loja atribui a própria chave
    assert {"manifest.json", "background.js", "content.js", "rtc.js", "parser.js", "pairing.html"} <= nomes
    assert not {"README.md", "config.js", "LOJA.md"} & nomes
    assert not any(n.startswith(("tests/", ".")) or n.endswith((".test.js", ".map")) for n in nomes)


def test_versao_confere(tmp_path):
    with zipfile.ZipFile(_zip(tmp_path)) as z:
        assert json.loads(z.read("manifest.json"))["version"] == config.VERSAO


def test_versao_divergente_recusada(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "VERSAO", "0.0.1")
    with pytest.raises(ValueError, match="versão"):
        _zip(tmp_path)


def test_permissoes_minimas(tmp_path):
    with zipfile.ZipFile(_zip(tmp_path)) as z:
        manifesto = json.loads(z.read("manifest.json"))
    assert sorted(manifesto["permissions"]) == ["nativeMessaging", "storage"]
    assert manifesto["host_permissions"] == ["https://meet.google.com/*"]
    assert "<all_urls>" not in json.dumps(manifesto)


def test_zip_deterministico(tmp_path):
    a, b = _zip(tmp_path, "a.zip"), _zip(tmp_path, "b.zip")
    assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def test_politica_de_privacidade_e_textos_da_loja():
    politica = (RAIZ / "docs" / "PRIVACIDADE-EXTENSAO.md").read_text(encoding="utf-8")
    assert "127.0.0.1" in politica and "não envia" in politica
    loja = (RAIZ / "extension" / "meet" / "LOJA.md").read_text(encoding="utf-8")
    for permissao in ("nativeMessaging", "storage", "meet.google.com"):
        assert permissao in loja
