# -*- coding: utf-8 -*-
"""Testes de segurança do assistente (Fase 1 — SEC-1, FR-1.3/1.4)."""
import pytest

from assistente import app, caminho_transcricao_seguro
from tests.front_assistente import HTML


def test_rejeita_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    assert caminho_transcricao_seguro("../../etc/passwd") is None
    assert caminho_transcricao_seguro("..\\..\\windows\\win.ini") is None
    assert caminho_transcricao_seguro("../../windows/system.ini") is None


def test_aceita_arquivo_valido(tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "ok.txt").write_text("x", encoding="utf-8")
    result = caminho_transcricao_seguro("ok.txt")
    assert result is not None
    assert result.endswith("ok.txt")


def test_rejeita_arquivo_inexistente(tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    assert caminho_transcricao_seguro("nao_existe.txt") is None


def test_api_chat_rejeita_path_traversal(tmp_path, monkeypatch, headers_token):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    client = app.test_client()
    resp = client.post(
        "/api/chat",
        json={
            "modelo": "test",
            "transcricao": "../../config.py",
            "pergunta": "teste",
        },
        headers=headers_token,
    )
    # E3: validador barra traversal no payload (400); caminho real segue 403.
    assert resp.status_code == 400
    assert resp.get_json() == {"erro": "campo transcricao inválido"}


def test_api_chat_rejeita_corpo_nao_objeto(tmp_path, monkeypatch, headers_token):
    from assistente import app

    client = app.test_client()
    for corpo in ("texto", "42", "[1,2]", "null"):
        resp = client.post(
            "/api/chat", data=corpo, content_type="application/json", headers=headers_token
        )
        assert resp.status_code == 400, corpo
        assert resp.get_json() == {"erro": "corpo deve ser objeto"}


def test_api_chat_rejeita_historico_invalido(tmp_path, monkeypatch, headers_token):
    from assistente import app

    client = app.test_client()
    base = {"modelo": "m", "transcricao": "r.txt", "pergunta": "p"}
    for historico in ([["x"]], [{"role": "admin", "content": "x"}], [{"role": "user", "content": ""}]):
        resp = client.post(
            "/api/chat", json=dict(base, historico=historico), headers=headers_token
        )
        assert resp.status_code == 400
        assert set(resp.get_json()) == {"erro"}


def test_api_chat_rejeita_origem_e_host(tmp_path, monkeypatch, headers_token):
    from assistente import app

    client = app.test_client()
    corpo = {"modelo": "m", "transcricao": "r.txt", "pergunta": "p", "historico": []}
    resp = client.post("/api/chat", json=corpo, headers={**headers_token, "Origin": "https://evil.example.test"})
    assert resp.status_code == 403
    resp = client.post("/api/chat", json=corpo, headers=headers_token, base_url="http://evil.example.test")
    assert resp.status_code == 403


def test_api_chat_corpo_grande_413(tmp_path, monkeypatch, headers_token):
    from assistente import app

    client = app.test_client()
    resp = client.post(
        "/api/chat",
        json={"modelo": "m", "transcricao": "r.txt", "pergunta": "p" * 300_000, "historico": []},
        headers=headers_token,
    )
    assert resp.status_code == 413
    assert resp.get_json() == {"erro": "Corpo da requisição muito grande"}


def test_api_chat_concorrencia_429(tmp_path, monkeypatch, headers_token):
    import assistente
    from assistente import app

    monkeypatch.setattr(assistente, "_semaforo_chat", __import__("threading").BoundedSemaphore(1))
    (tmp_path / "r.txt").write_text("conteudo", encoding="utf-8")
    monkeypatch.setattr(assistente, "PASTA_TRANSCRICOES", str(tmp_path))
    assistente._semaforo_chat.acquire()
    try:
        resp = app.test_client().post(
            "/api/chat",
            json={"modelo": "m", "transcricao": "r.txt", "pergunta": "p", "historico": []},
            headers=headers_token,
        )
        assert resp.status_code == 429
        assert resp.get_json() == {"erro": "Muitas requisições simultâneas"}
    finally:
        assistente._semaforo_chat.release()


def test_api_chat_nunca_500_e_sem_eco(tmp_path, monkeypatch, headers_token):
    from assistente import app

    client = app.test_client()
    segredo = "segredo-super-sensivel-123"
    corpos = [
        {"modelo": segredo, "transcricao": "r.txt", "pergunta": "p"},
        {"modelo": "m", "transcricao": segredo, "pergunta": "p"},
        {"modelo": "m", "transcricao": "r.txt", "pergunta": segredo * 100},
        {"modelo": "m", "transcricao": "r.txt", "pergunta": "p", "historico": "nao-lista"},
        {"modelo": "m", "transcricao": "r.txt", "pergunta": "p", "historico": [{"role": "user"}]},
    ]
    for corpo in corpos:
        resp = client.post("/api/chat", json=corpo, headers=headers_token)
        assert resp.status_code in (400, 403, 413)
        assert segredo * 10 not in resp.get_data(as_text=True)


def test_cabecalhos_privacidade(tmp_path, monkeypatch, headers_token):
    from assistente import app

    client = app.test_client()
    resp = client.get("/api/transcricoes", headers=headers_token)
    assert resp.headers.get("Cache-Control") == "no-store"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "frame-ancestors 'none'" in resp.headers.get("Content-Security-Policy", "")


def test_desconexao_fecha_upstream():
    from assistente_ollama import stream_chat_ollama

    fechado = []

    class _Resp:
        def __iter__(self):
            yield b'{"message": {"content": "oi"}, "done": false}'
            yield b'{"message": {"content": "oi"}, "done": true}'

        def close(self):
            fechado.append(True)

    import assistente_ollama

    orig = assistente_ollama.urllib.request.urlopen
    assistente_ollama.urllib.request.urlopen = lambda *a, **k: _Resp()
    try:
        gen = stream_chat_ollama(object()).response
        next(gen)
        gen.close()
    finally:
        assistente_ollama.urllib.request.urlopen = orig
    assert fechado == [True]


def test_html_usa_build_select_options_sem_innerhtml_dados():
    assert "function buildSelectOptions" in HTML
    inicio = HTML.find("async function loadList")
    assert inicio != -1
    bloco = HTML[inicio : inicio + 1200]
    assert "buildSelectOptions" in bloco
    assert "selTrans.innerHTML = d.map" not in bloco


def test_html_modelos_usa_build_model_options_sem_innerhtml():
    assert "function buildModelOptions" in HTML
    inicio = HTML.find("async function loadList")
    bloco = HTML[inicio : inicio + 1500]
    assert "buildModelOptions" in bloco
    assert "selMod.innerHTML = d.map" not in bloco