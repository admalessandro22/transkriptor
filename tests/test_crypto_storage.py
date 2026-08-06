# -*- coding: utf-8 -*-
"""Testes de criptografia em repouso (FR-3.1–3.8, SEC-8/9)."""
import json
from pathlib import Path

import numpy as np
import pytest

from crypto_storage import (
    MAGIC_HEADER,
    ErroDescriptografia,
    criptografar_bytes,
    descriptografar_bytes,
    garantir_chave_mestra,
    ler_bytes_arquivo,
    ler_transcricao,
    migrar_txt_legacy,
    migrar_vozes_legacy,
    salvar_bytes_arquivo,
    salvar_transcricao,
)


def test_roundtrip_bytes(chave_teste):
    plano = b"frase secreta da reuniao com dados sensiveis"
    cifrado = criptografar_bytes(plano)
    assert descriptografar_bytes(cifrado) == plano


def test_header_tkpt1(chave_teste):
    cifrado = criptografar_bytes(b"x")
    assert cifrado.startswith(MAGIC_HEADER)


def test_arquivo_em_disco_nao_contem_plaintext(chave_teste, tmp_path):
    frase = "conteudo confidencial da reuniao de diretoria"
    caminho = tmp_path / "reuniao.tkpt"
    salvar_transcricao(str(caminho), frase)
    raw = caminho.read_bytes()
    assert frase.encode("utf-8") not in raw
    assert ler_transcricao("reuniao.tkpt", str(tmp_path)) == frase


def test_descriptografar_invalido_erro_generico(chave_teste):
    with pytest.raises(ErroDescriptografia) as exc:
        descriptografar_bytes(b"TKPT1" + b"\x00" * 20)
    assert "Transkriptor" in str(exc.value)


def test_migrar_txt_legacy_remove_plaintext(chave_teste, tmp_path):
    legado = tmp_path / "antiga.txt"
    legado.write_text("=== Transcricao ===\n\nola mundo", encoding="utf-8")
    qtd = migrar_txt_legacy(str(tmp_path))
    assert qtd == 1
    assert not legado.exists()
    assert not (tmp_path / "antiga.txt.bak").exists()
    assert (tmp_path / "antiga.tkpt").is_file()
    assert ler_transcricao("antiga.tkpt", str(tmp_path)).startswith("=== Transcricao")


def test_migrar_txt_legacy_backup_opt_in(chave_teste, tmp_path, monkeypatch):
    cfg = Path(chave_teste)
    cfg.write_text(json.dumps({"backup_txt_na_migracao": True}), encoding="utf-8")
    legado = tmp_path / "antiga.txt"
    legado.write_text("conteudo legado", encoding="utf-8")
    qtd = migrar_txt_legacy(str(tmp_path))
    assert qtd == 1
    assert not legado.exists()
    assert (tmp_path / "antiga.txt.bak").is_file()
    assert (tmp_path / "antiga.tkpt").is_file()


def test_migrar_txt_colisao_tkpt_valido_preserva_existente(chave_teste, tmp_path):
    legado = tmp_path / "antiga.txt"
    legado.write_text("texto legado que nao deve sobrescrever", encoding="utf-8")
    existente = tmp_path / "antiga.tkpt"
    salvar_transcricao(str(existente), "versao criptografada anterior")
    antes = existente.read_bytes()
    qtd = migrar_txt_legacy(str(tmp_path))
    assert qtd == 0
    assert not legado.exists()
    assert existente.read_bytes() == antes
    assert ler_transcricao("antiga.tkpt", str(tmp_path)) == "versao criptografada anterior"


def test_migrar_txt_colisao_tkpt_corrupto_usa_sufixo(chave_teste, tmp_path):
    legado = tmp_path / "antiga.txt"
    legado.write_text("conteudo migrado", encoding="utf-8")
    corrupto = tmp_path / "antiga.tkpt"
    corrupto.write_bytes(b"TKPT1" + b"\x00" * 20)
    qtd = migrar_txt_legacy(str(tmp_path))
    assert qtd == 1
    assert not legado.exists()
    migrado = tmp_path / "antiga_migrado_001.tkpt"
    assert migrado.is_file()
    assert ler_transcricao("antiga_migrado_001.tkpt", str(tmp_path)) == "conteudo migrado"


def test_dpapi_falha_nao_rotaciona_chave(tmp_path, monkeypatch):
    import config_user
    import crypto_storage

    cfg = tmp_path / "config_user.json"
    chave_dpapi = tmp_path / "transkriptor_key.dpapi"
    blob_original = "Y2hhdmUtdGVzdGU="
    cfg.write_text(json.dumps({"chave_dpapi": blob_original}), encoding="utf-8")
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(cfg))
    monkeypatch.setattr(crypto_storage._config, "ARQUIVO_CHAVE_DPAPI", str(chave_dpapi))
    monkeypatch.setattr(crypto_storage, "_chave_mestra", None)

    def falha_unprotect(_data):
        raise OSError("CryptUnprotectData falhou")

    monkeypatch.setattr(crypto_storage, "_dpapi_unprotect", falha_unprotect)
    monkeypatch.setattr(crypto_storage, "_dpapi_protect", lambda b: b"DPAPI:" + b)

    assert garantir_chave_mestra() is False
    assert json.loads(cfg.read_text(encoding="utf-8"))["chave_dpapi"] == blob_original


def test_chave_dedicada_sobrevive_a_salvamento_de_config_stale(tmp_path, monkeypatch):
    """SEC-10.F1: a chave não pode depender do JSON sobrescrito no bootstrap."""
    import config_user
    import crypto_storage

    cfg = tmp_path / "config_user.json"
    chave_dpapi = tmp_path / "transkriptor_key.dpapi"
    cfg.write_text(json.dumps({"meet_bridge_token": "token-preservado"}), encoding="utf-8")
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(cfg))
    monkeypatch.setattr(crypto_storage._config, "ARQUIVO_CHAVE_DPAPI", str(chave_dpapi))
    monkeypatch.setattr(crypto_storage, "_dpapi_protect", lambda b: b"DPAPI:" + b)
    monkeypatch.setattr(crypto_storage, "_dpapi_unprotect", lambda b: b[6:])
    monkeypatch.setattr(crypto_storage, "_chave_mestra", None)

    assert garantir_chave_mestra() is True
    chave_original = crypto_storage._chave_mestra
    assert chave_dpapi.read_bytes() == b"DPAPI:" + chave_original

    # Reproduz o defeito real: um snapshot antigo do bootstrap substitui o JSON.
    config_user.salvar({"modelo_whisper": "small"})
    monkeypatch.setattr(crypto_storage, "_chave_mestra", None)

    assert garantir_chave_mestra() is True
    assert crypto_storage._chave_mestra == chave_original


def test_chave_legada_e_migrada_para_arquivo_dedicado(tmp_path, monkeypatch):
    """SEC-10.F2: instalações antigas mantêm a chave ao adotar o arquivo dedicado."""
    import config_user
    import crypto_storage

    chave = b"k" * crypto_storage.KEY_SIZE
    protegido = b"DPAPI:" + chave
    cfg = tmp_path / "config_user.json"
    chave_dpapi = tmp_path / "transkriptor_key.dpapi"
    cfg.write_text(
        json.dumps({"chave_dpapi": __import__("base64").b64encode(protegido).decode("ascii")}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(cfg))
    monkeypatch.setattr(crypto_storage._config, "ARQUIVO_CHAVE_DPAPI", str(chave_dpapi))
    monkeypatch.setattr(crypto_storage, "_dpapi_unprotect", lambda b: b[6:])
    monkeypatch.setattr(crypto_storage, "_chave_mestra", None)

    assert garantir_chave_mestra() is True
    assert crypto_storage._chave_mestra == chave
    assert chave_dpapi.read_bytes() == protegido


def test_migrar_vozes_legacy_npz_e_json(chave_teste, tmp_path):
    modelo = tmp_path / "_modelo_voz"
    modelo.mkdir()
    npz = modelo / "perfil_usuario.npz"
    buf = __import__("io").BytesIO()
    np.savez(buf, embedding=np.array([1.0, 2.0], dtype=np.float32), versao=np.int32(1))
    npz.write_bytes(buf.getvalue())
    json_path = modelo / "vozes_conhecidas.json"
    json_path.write_text(
        json.dumps({"Ana": {"rotulo_origem": "Falante 1", "embedding": [0.1, 0.2]}}),
        encoding="utf-8",
    )
    enc_perfil = modelo / "perfil_usuario.enc"
    enc_vozes = modelo / "vozes_conhecidas.enc"

    qtd = migrar_vozes_legacy(str(npz), str(enc_perfil), str(json_path), str(enc_vozes))
    assert qtd == 2
    assert not npz.exists()
    assert not json_path.exists()
    assert enc_perfil.is_file()
    assert enc_vozes.is_file()
    assert b"Ana" not in enc_vozes.read_bytes()
    assert ler_bytes_arquivo(str(enc_perfil)) == buf.getvalue()


def test_salvar_ler_bytes_perfil(chave_teste, tmp_path):
    caminho = tmp_path / "perfil_usuario.enc"
    payload = b"npz-fake-bytes"
    salvar_bytes_arquivo(str(caminho), payload)
    assert payload not in caminho.read_bytes()
    assert ler_bytes_arquivo(str(caminho)) == payload


def test_assistente_ler_tkpt_via_modulo(chave_teste, tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    salvar_transcricao(str(tmp_path / "meet.tkpt"), "linha da reuniao")
    from assistente import ler_conteudo_transcricao

    assert ler_conteudo_transcricao("meet.tkpt") == "linha da reuniao"
    assert ler_conteudo_transcricao("../../etc/passwd") is None
