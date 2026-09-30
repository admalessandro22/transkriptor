# -*- coding: utf-8 -*-
"""T-15.D3 / UX-15.D3 — Configurações de IA: Whisper, resumo e chat (Ollama ou OpenRouter)."""
from __future__ import annotations

import pytest

import config_user
from tests.fake_ollama import FakeOllama

CHAVE = "sk-or-v1-segredo-sintetico-123456"


@pytest.fixture
def cliente(monkeypatch):
    from assistente import app

    monkeypatch.setattr("central_ia._hardware", lambda: (False, 0.0))
    return app.test_client()


@pytest.fixture
def fake(monkeypatch):
    f = FakeOllama(modelos=["granite4.1:3b", "gemma4:latest"])
    f.start()
    monkeypatch.setattr("config.OLLAMA_URL", f.url)
    yield f
    f.stop()


def _post(cliente, headers, **corpo):
    return cliente.post("/api/ia", json=corpo, headers=headers)


def test_estado_sem_chave_nem_texto(cliente, headers_token):
    config_user.atualizar(ia_resumo_modelo="granite4.1:3b")
    dados = cliente.get("/api/ia", headers=headers_token).get_json()
    assert dados["resumo"] == {"provedor": "ollama", "modelo": "granite4.1:3b"}
    assert dados["chat"]["provedor"] == "ollama"
    assert dados["transcricao"]["dispositivo"] == "auto" and dados["transcricao"]["recomendado"] == "small"
    assert dados["openrouter"] == {"configurada": False, "final": None, "consentido_em": None}


def test_modelos_do_provedor(cliente, headers_token, fake):
    dados = cliente.get("/api/ia/modelos?provedor=ollama", headers=headers_token).get_json()
    assert dados["estado"]["estado"] == "online"
    assert [m["id"] for m in dados["modelos"]] == ["granite4.1:3b", "gemma4:latest"]


def test_modelos_openrouter_sem_chave_explica(cliente, headers_token):
    dados = cliente.get("/api/ia/modelos?provedor=openrouter", headers=headers_token).get_json()
    assert dados["estado"]["estado"] == "sem_chave" and dados["modelos"] == []


def test_openrouter_exige_confirmacao(cliente, headers_token):
    r = _post(cliente, headers_token, chave="ia_resumo_provedor", valor="openrouter")
    assert r.status_code == 409
    corpo = r.get_json()
    assert "Áudio e voz nunca saem" in corpo["consequencia"]
    assert config_user.carregar().get("ia_resumo_provedor") in (None, "ollama")
    r = _post(cliente, headers_token, chave="ia_resumo_provedor", valor="openrouter", confirmado=True)
    assert r.status_code == 200 and r.get_json()["resumo"]["provedor"] == "openrouter"
    assert config_user.carregar()["openrouter_consentido_em"]
    # já consentido: o chat não pergunta de novo
    assert _post(cliente, headers_token, chave="ia_chat_provedor", valor="openrouter").status_code == 200


def test_revogar_consentimento_volta_ao_ollama(cliente, headers_token):
    _post(cliente, headers_token, chave="ia_chat_provedor", valor="openrouter", confirmado=True)
    dados = _post(cliente, headers_token, chave="openrouter_consentimento", valor=False).get_json()
    assert dados["chat"]["provedor"] == "ollama" and dados["openrouter"]["consentido_em"] is None


def test_chave_nao_retorna(cliente, headers_token):
    r = _post(cliente, headers_token, chave="openrouter_chave", valor=CHAVE)
    assert r.status_code == 200
    assert CHAVE not in r.get_data(as_text=True)
    assert r.get_json()["openrouter"] == {"configurada": True, "final": "3456", "consentido_em": None}
    assert CHAVE not in cliente.get("/api/ia", headers=headers_token).get_data(as_text=True)


@pytest.mark.parametrize("chave,valor", [
    ("whisper_dispositivo", "tpu"), ("whisper_precisao", "int4"), ("ia_chat_provedor", "outro"),
    ("ia_resumo_modelo", "x" * 121), ("ollama_url", "http://192.168.0.9:11434"), ("desconhecida", 1),
])
def test_valores_invalidos_recusados(cliente, headers_token, chave, valor):
    assert _post(cliente, headers_token, chave=chave, valor=valor).status_code == 400


def test_url_do_ollama_normalizada(cliente, headers_token):
    dados = _post(cliente, headers_token, chave="ollama_url", valor="localhost:8080").get_json()
    assert dados["ollama_url"] == "http://localhost:8080"


def test_resumo_usa_modelo_configurado(cliente, headers_token, fake):
    import central_resumos

    _post(cliente, headers_token, chave="ia_resumo_modelo", valor="gemma4:latest")
    assert central_resumos._modelos_instalados()[0] == "gemma4:latest"


def test_testar_sem_transcricao(cliente, headers_token, fake):
    r = cliente.post("/api/ia/testar", json={"provedor": "ollama", "modelo": "granite4.1:3b"}, headers=headers_token)
    dados = r.get_json()
    assert dados["ok"] is True and isinstance(dados["latencia_ms"], int)
    corpo = [p for p in fake.requests if p["path"].startswith("/api/chat")][-1]["body"]
    assert "transcri" not in str(corpo["messages"]).lower()


def test_mutacao_exige_header_secreto(cliente):
    assert cliente.post("/api/ia", json={"chave": "whisper_dispositivo", "valor": "cpu"}).status_code == 403


def test_whisper_dispositivo_aplicado(monkeypatch):
    """CPU escolhida: "auto" não tenta GPU e cai no modelo leve; precisão de CPU."""
    from unittest.mock import MagicMock, patch

    from transcricao_core import Transcritor

    config_user.atualizar(whisper_dispositivo="cpu")
    monkeypatch.setattr("transcricao_core.detectar_cuda_e_vram", lambda: (True, 8.0))
    t = Transcritor(modelo="auto", diarizar_ao_final=False)
    with patch("transcricao_core.WhisperModel", return_value=MagicMock()) as wm:
        t._carregar_modelo()
    wm.assert_called_once_with("small", device="cpu", compute_type="int8")

    config_user.atualizar(whisper_dispositivo="auto", whisper_precisao="float16")
    t = Transcritor(modelo="base", diarizar_ao_final=False)
    with patch("transcricao_core.WhisperModel", return_value=MagicMock()) as wm, \
            patch("transcricao_core.resolver_device_whisper", return_value="cuda"):
        t._carregar_modelo()
    wm.assert_called_once_with("base", device="cuda", compute_type="float16")


def test_chat_usa_modelo_escolhido_como_padrao(cliente, headers_token, fake):
    """/api/modelos põe o modelo do chat escolhido primeiro: é o que o chat seleciona."""
    assert cliente.get("/api/modelos", headers=headers_token).get_json()[0] == "granite4.1:3b"
    _post(cliente, headers_token, chave="ia_chat_modelo", valor="gemma4:latest")
    assert cliente.get("/api/modelos", headers=headers_token).get_json() == ["gemma4:latest", "granite4.1:3b"]


def test_chat_openrouter_lista_o_modelo_escolhido(cliente, headers_token):
    import provedor_openrouter as po

    po.salvar_chave(CHAVE)
    _post(cliente, headers_token, chave="ia_chat_provedor", valor="openrouter", confirmado=True)
    _post(cliente, headers_token, chave="ia_chat_modelo", valor="org/conversador")
    assert cliente.get("/api/modelos", headers=headers_token).get_json() == ["org/conversador"]
