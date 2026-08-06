# -*- coding: utf-8 -*-
"""Testes do módulo config_user (FR-6.5, NFR-6.1)."""
import json
import threading
from pathlib import Path

import config_user


def test_carregar_inexistente_retorna_vazio(tmp_path, monkeypatch):
    """FR-6.5: carregar() sem arquivo → dict vazio."""
    caminho = tmp_path / "config_user.json"
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(caminho))
    assert config_user.carregar() == {}


def test_salvar_e_carregar_roundtrip(tmp_path, monkeypatch):
    """FR-6.5: salvar + carregar preserva o dict."""
    caminho = tmp_path / "config_user.json"
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(caminho))
    config_user.salvar({"versao_config": 2, "modelo_whisper": "auto"})
    assert config_user.carregar() == {"versao_config": 2, "modelo_whisper": "auto"}
    assert caminho.is_file()


def test_atualizar_mescla_chaves(tmp_path, monkeypatch):
    """FR-6.5: atualizar(**kv) mescla sem apagar outras chaves."""
    caminho = tmp_path / "config_user.json"
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(caminho))
    config_user.salvar({"a": 1, "b": 2})
    out = config_user.atualizar(b=3, c=4)
    assert out == {"a": 1, "b": 3, "c": 4}
    assert config_user.carregar() == {"a": 1, "b": 3, "c": 4}


def test_bootstrap_atualiza_sem_apagar_chaves_concorrentes(tmp_path, monkeypatch):
    """SEC-10.F2: defaults do bootstrap usam merge, nunca snapshot stale."""
    import app_bootstrap

    caminho = tmp_path / "config_user.json"
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(caminho))
    config_user.salvar({"meet_bridge_token": "abc", "preferencia_usuario": True})

    app_bootstrap.atualizar_config_user(criptografar_transcricoes=True)

    assert config_user.carregar() == {
        "meet_bridge_token": "abc",
        "preferencia_usuario": True,
        "criptografar_transcricoes": True,
    }


def test_escrita_atomica_usa_replace(tmp_path, monkeypatch):
    """FR-6.5: escrita via tmp + os.replace (sem deixar JSON parcial)."""
    caminho = tmp_path / "config_user.json"
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(caminho))
    replaces = []
    original = config_user.os.replace

    def _spy_replace(src, dst):
        replaces.append((str(src), str(dst)))
        return original(src, dst)

    monkeypatch.setattr(config_user.os, "replace", _spy_replace)
    config_user.salvar({"ok": True})
    assert len(replaces) == 1
    src, dst = replaces[0]
    assert dst == str(caminho)
    assert src != dst
    assert json.loads(caminho.read_text(encoding="utf-8")) == {"ok": True}


def test_concorrencia_duas_threads_50_atualizacoes(tmp_path, monkeypatch):
    """FR-6.5: 2 threads × 50 atualizações → JSON válido com todas as chaves."""
    caminho = tmp_path / "config_user.json"
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(caminho))
    config_user.salvar({})
    erros = []

    def _worker(prefix, n=50):
        try:
            for i in range(n):
                config_user.atualizar(**{f"{prefix}_{i}": i})
        except Exception as e:
            erros.append(e)

    t1 = threading.Thread(target=_worker, args=("a",))
    t2 = threading.Thread(target=_worker, args=("b",))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not erros
    cfg = config_user.carregar()
    assert isinstance(cfg, dict)
    for i in range(50):
        assert cfg[f"a_{i}"] == i
        assert cfg[f"b_{i}"] == i
    # JSON no disco é parseável
    json.loads(caminho.read_text(encoding="utf-8"))


def test_nfr_somente_config_user_abre_arquivo():
    """NFR-6.1: só config_user.py abre config_user.json diretamente."""
    raiz = Path(__file__).resolve().parent.parent
    ofensores = []
    # Produção: .py e .pyw na raiz (exclui tests/ e scripts/)
    for caminho in list(raiz.glob("*.py")) + list(raiz.glob("*.pyw")):
        if caminho.name == "config_user.py":
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, linha in enumerate(texto.splitlines(), 1):
            if "config_user.json" not in linha:
                continue
            # Constante de path sozinha é ok; I/O na mesma linha não
            if any(
                tok in linha
                for tok in ("open(", "json.load", "json.dump", "write_text", "read_text")
            ):
                ofensores.append(f"{caminho.name}:{i}:{linha.strip()}")
        # open(CONFIG_USER_FILE) / open(CONFIG_USER) sem a string literal
        for i, linha in enumerate(texto.splitlines(), 1):
            if "open(" not in linha:
                continue
            if "CONFIG_USER_FILE" in linha or "CONFIG_USER" in linha:
                # não contar se for só comentário
                if linha.lstrip().startswith("#"):
                    continue
                ofensores.append(f"{caminho.name}:{i}:{linha.strip()}")
    assert ofensores == [], f"I/O direto em config_user.json fora de config_user.py: {ofensores}"
