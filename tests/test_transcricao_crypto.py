# -*- coding: utf-8 -*-
"""Testes de gravação criptografada no Transcritor (FR-3.2/3.3)."""
import io
from unittest.mock import patch

from crypto_storage import ler_transcricao
from transcricao_core import Transcritor


def test_transcritor_grava_tkpt_sem_plaintext_em_disco(chave_teste, tmp_path, monkeypatch):
    monkeypatch.setattr("crypto_storage.CONFIG_USER_FILE", chave_teste)
    t = Transcritor(pasta_saida=str(tmp_path), diarizar_ao_final=False, criptografar=True)
    t._abrir_arquivo()
    t._arq.write("linha sensivel da reuniao\n")
    t._finalizar_arquivo_texto()
    caminho = t._caminho_saida
    assert caminho.endswith(".tkpt")
    assert b"linha sensivel" not in open(caminho, "rb").read()
    assert "linha sensivel" in ler_transcricao(caminho.split("\\")[-1].split("/")[-1], str(tmp_path))


def test_transcritor_modo_legacy_txt_quando_crypto_off(tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), diarizar_ao_final=False, criptografar=False)
    t._abrir_arquivo()
    assert t._caminho_saida.endswith(".txt")
    assert not isinstance(t._arq, io.StringIO)