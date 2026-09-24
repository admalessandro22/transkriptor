# -*- coding: utf-8 -*-
"""T-13.E1 — política única de proteção e falha explícita (sem fallback)."""
from __future__ import annotations

import numpy as np
import pytest

from politica_privacidade import (
    ProtectionMode,
    ProtectionState,
    ProtectionUnavailable,
    inventariar_migracao,
    protect_artifact,
    resolve_initial_mode,
)


def test_instalacao_nova_protegida():
    assert resolve_initial_mode(None) == ProtectionMode.PROTECTED


def test_instalacao_existente_sem_campo_compativel():
    assert resolve_initial_mode({}) == ProtectionMode.COMPATIBLE
    assert resolve_initial_mode({"protection_mode": "compatible"}) == ProtectionMode.COMPATIBLE
    assert resolve_initial_mode({"protection_mode": "protected"}) == ProtectionMode.PROTECTED


def test_menu_ativa_protecao_apenas_com_confirmacao_e_chave(monkeypatch):
    import app_bandeja_menu
    import config_user
    import politica_privacidade

    alteracoes = []
    monkeypatch.setattr(config_user, "atualizar", lambda **kw: alteracoes.append(kw))
    monkeypatch.setattr(app_bandeja_menu, "chave_disponivel", lambda: True)
    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.COMPATIBLE)

    class Bandeja(app_bandeja_menu.MenuBandejaMixin):
        def _gravando(self): return False
        def _processamento_em_execucao(self): return False
        def _confirmar_modo_protegido(self): return True
        def _status(self, _texto): pass
        def _atualizar_tooltip(self): pass

    bandeja = Bandeja()
    bandeja.ativar_modo_protegido()
    assert alteracoes == [{"protection_mode": "protected"}]

    alteracoes.clear()
    monkeypatch.setattr(Bandeja, "_confirmar_modo_protegido", lambda self: False)
    bandeja.ativar_modo_protegido()
    assert alteracoes == []


def test_menu_recusa_protecao_durante_gravacao(monkeypatch):
    import app_bandeja_menu
    import config_user
    import politica_privacidade

    alteracoes = []
    monkeypatch.setattr(config_user, "atualizar", lambda **kw: alteracoes.append(kw))
    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.COMPATIBLE)

    class Bandeja(app_bandeja_menu.MenuBandejaMixin):
        def _gravando(self): return True
        def _processamento_em_execucao(self): return False
        def _status(self, _texto): pass

    Bandeja().ativar_modo_protegido()
    assert alteracoes == []


def test_menu_recusa_protecao_sem_chave(monkeypatch):
    import app_bandeja_menu
    import config_user
    import politica_privacidade

    alteracoes = []
    monkeypatch.setattr(config_user, "atualizar", lambda **kw: alteracoes.append(kw))
    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.COMPATIBLE)
    monkeypatch.setattr(app_bandeja_menu, "chave_disponivel", lambda: False)

    class Bandeja(app_bandeja_menu.MenuBandejaMixin):
        def _gravando(self): return False
        def _processamento_em_execucao(self): return False
        def _status(self, _texto): pass

    Bandeja().ativar_modo_protegido()
    assert alteracoes == []


def test_sem_chave_nao_salva_biometria_em_claro(tmp_path, monkeypatch):
    import crypto_storage
    import politica_privacidade
    from identificador_voz import salvar_perfil
    from politica_privacidade import ProtectionUnavailable

    monkeypatch.setattr(crypto_storage, "criptografia_ativa", lambda: True)
    monkeypatch.setattr(crypto_storage, "chave_disponivel", lambda: False)
    monkeypatch.setattr(
        politica_privacidade, "modo_efetivo", lambda: politica_privacidade.ProtectionMode.PROTECTED
    )
    alvo = tmp_path / "perfil.npz"
    with pytest.raises(ProtectionUnavailable):
        salvar_perfil(np.ones(192, dtype=np.float32), alvo)
    assert not alvo.exists()


def test_chave_corrompida_nao_regrava_blob(chave_teste, tmp_path, monkeypatch):
    import crypto_storage

    monkeypatch.setattr(crypto_storage, "_chave_mestra", None)
    blob = tmp_path / "transkriptor_key.dpapi"
    blob.write_bytes(b"lixo-corrompido")
    monkeypatch_chave = tmp_path / "sentinela.enc"
    monkeypatch_chave.write_bytes(b"conteudo-protegido")
    antes = monkeypatch_chave.read_bytes()
    assert crypto_storage.chave_disponivel() is False
    assert blob.read_bytes() == b"lixo-corrompido"
    assert monkeypatch_chave.read_bytes() == antes


def test_falha_cifra_preserva_audio_em_area_restrita(tmp_path, monkeypatch):
    import crypto_storage

    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 100)
    monkeypatch.setattr(
        crypto_storage, "salvar_bytes_arquivo", lambda *a, **k: (_ for _ in ()).throw(OSError("cifra falhou"))
    )
    protecao = protect_artifact(wav, ProtectionMode.PROTECTED)
    assert protecao.state == ProtectionState.PROTECTION_PENDING
    assert (tmp_path / "restrito" / "audio.wav").read_bytes() == b"RIFF" + b"\x00" * 100
    assert not wav.exists()


def test_troca_modo_nao_rebaixa_protegido(chave_teste, tmp_path):
    from crypto_storage import salvar_bytes_arquivo

    salvar_bytes_arquivo(str(tmp_path / "a.wav.enc"), b"audio-protegido")
    protecao = protect_artifact(tmp_path / "a.wav.enc", ProtectionMode.COMPATIBLE)
    assert protecao.state == ProtectionState.PROTECTED
    assert not (tmp_path / "a.wav").exists()


def test_modo_protegido_prevalece_sobre_flag_legada(chave_teste, tmp_path, monkeypatch):
    import crypto_storage

    monkeypatch.setattr(crypto_storage, "criptografia_ativa", lambda: False)
    caminho = tmp_path / "resultado.txt"
    caminho.write_text("conteúdo sensível", encoding="utf-8")
    protecao = protect_artifact(caminho, ProtectionMode.PROTECTED)
    assert protecao.state == ProtectionState.PROTECTED
    assert not caminho.exists()
    assert crypto_storage.ler_bytes_arquivo(str(tmp_path / protecao.relative_path)) == "conteúdo sensível".encode("utf-8")


def test_dry_run_nao_remove(tmp_path):
    (tmp_path / "r.txt").write_text("legado", encoding="utf-8")
    candidatos, _ = inventariar_migracao(tmp_path)
    assert candidatos
    from politica_privacidade import aplicar_migracao_confirmada

    removidos = aplicar_migracao_confirmada(tmp_path, candidatos, confirmados=[], dry_run=True)
    assert removidos == []
    assert (tmp_path / "r.txt").is_file()
    removidos = aplicar_migracao_confirmada(tmp_path, candidatos, confirmados=list(candidatos), dry_run=False)
    assert removidos == list(candidatos)
    assert not (tmp_path / "r.txt").exists()
