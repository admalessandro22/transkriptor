# -*- coding: utf-8 -*-
"""Assistente de reunião — Flask local (Ollama) com front em templates/static."""

import datetime
import json
import os
import secrets
import socket
import threading
import time
import urllib.request

from flask import Flask, jsonify, make_response, redirect, render_template, request

from assistente_ollama import (
    _cache_ctx,
    chamar_ollama_sync as _chamar_ollama_sync,
    consultar_context_length,
    orcamento_chars,
    processar_chat,
)
from config import (
    BASE_DIR,
    MAX_CHARS_TRANSCRICAO,
    MAX_CORPO_CHAT_BYTES,
    MAX_HISTORICO_CHAT,
    OLLAMA_TIMEOUT_CONEXAO,
    OLLAMA_URL,
    PASTA_TRANSCRICOES,
    PORTAS_FALLBACK,
    ROTULO_USUARIO,
    VERSAO,
)

app = Flask(__name__, root_path=str(BASE_DIR))

HEADER_TOKEN = "X-Transkriptor-Token"
COOKIE_TOKEN = "tkpt_token"
SESSAO_TOKEN = os.environ.get("TRANSKRIPTOR_TOKEN") or secrets.token_urlsafe(32)


def obter_token_sessao():
    return SESSAO_TOKEN


def token_requisicao_valido() -> bool:
    """Aceita token no header ou cookie HttpOnly — rejeita query em /api/* (SEC-4.1)."""
    if request.headers.get(HEADER_TOKEN) == SESSAO_TOKEN:
        return True
    return request.cookies.get(COOKIE_TOKEN) == SESSAO_TOKEN


@app.before_request
def verificar_token():
    if request.path.startswith("/api/"):
        if request.args.get("token"):
            return jsonify({"erro": "Token inválido"}), 403
        if not token_requisicao_valido():
            return jsonify({"erro": "Token inválido"}), 403


def _extensao_transcricao_permitida(nome: str) -> bool:
    return nome.endswith(".txt") or nome.endswith(".tkpt")


def caminho_transcricao_seguro(nome: str):
    """Retorna path absoluto seguro ou None se inválido/inexistente."""
    if not nome or ".." in nome.replace("\\", "/"):
        return None
    if not _extensao_transcricao_permitida(nome):
        return None
    base = os.path.realpath(PASTA_TRANSCRICOES)
    caminho = os.path.realpath(os.path.join(PASTA_TRANSCRICOES, nome))
    if not caminho.startswith(base + os.sep) and caminho != base:
        return None
    if not os.path.isfile(caminho):
        return None
    return caminho


def rotulo_usuario_efetivo() -> str:
    """Lê rotulo_usuario de config_user.json; fallback para ROTULO_USUARIO (FR-5.7)."""
    try:
        import config_user

        valor = config_user.carregar().get("rotulo_usuario")
        if valor:
            return str(valor)
    except Exception:
        pass
    return ROTULO_USUARIO


def transcricao_contem_voce(conteudo: str, rotulo: str | None = None) -> bool:
    """True se diarização inclui o rótulo efetivo do usuário (FR-5.7)."""
    rotulo_efetivo = rotulo if rotulo is not None else ROTULO_USUARIO
    return bool(rotulo_efetivo) and rotulo_efetivo in conteudo


def ler_conteudo_transcricao(nome: str) -> str | None:
    """Único caminho de leitura de transcrições para a API (FR-3.4)."""
    if not caminho_transcricao_seguro(nome):
        return None
    try:
        from crypto_storage import ErroDescriptografia, ler_transcricao

        return ler_transcricao(nome, PASTA_TRANSCRICOES)
    except ErroDescriptografia:
        return None


def iniciar_servidor_em_thread(flask_app, host, port):
    def _run():
        flask_app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def aguardar_servidor(url, timeout=10, intervalo=0.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(intervalo)
    return False


@app.route("/")
def index():
    token_q = request.args.get("token")
    if token_q and token_q == SESSAO_TOKEN:
        resp = make_response(redirect("/", code=302))
        resp.set_cookie(
            COOKIE_TOKEN, SESSAO_TOKEN, httponly=True, samesite="Strict", path="/"
        )
        return resp
    return render_template("assistente.html")


@app.route("/api/saude")
def api_saude():
    ollama_ok = False
    modelos: list[str] = []
    try:
        with urllib.request.urlopen(
            OLLAMA_URL.rstrip("/") + "/api/tags", timeout=OLLAMA_TIMEOUT_CONEXAO
        ) as r:
            dados = json.loads(r.read().decode("utf-8"))
        ollama_ok = True
        modelos = [m.get("name", "") for m in dados.get("models", []) if m.get("name")]
    except Exception:
        pass
    return jsonify({"ollama": ollama_ok, "modelos": modelos, "versao": VERSAO})


@app.route("/api/transcricoes")
def api_transcricoes():
    os.makedirs(PASTA_TRANSCRICOES, exist_ok=True)
    arquivos = sorted(
        f
        for f in os.listdir(PASTA_TRANSCRICOES)
        if _extensao_transcricao_permitida(f)
        and os.path.isfile(os.path.join(PASTA_TRANSCRICOES, f))
    )
    resultado = []
    rotulo = rotulo_usuario_efetivo()
    for nome in arquivos:
        caminho = os.path.join(PASTA_TRANSCRICOES, nome)
        stat = os.stat(caminho)
        preview, conteudo = "", ""
        try:
            conteudo = ler_conteudo_transcricao(nome) or ""
            linhas = [
                l.strip()
                for l in conteudo[:500].split("\n")
                if l.strip() and not l.startswith("===")
            ]
            preview = linhas[0][:80] if linhas else ""
        except Exception:
            pass
        tipo = "diarizado" if "_diarizado" in nome else "transcricao"
        resultado.append({
            "arquivo": nome,
            "data": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
            "tipo": tipo,
            "tamanho_kb": round(stat.st_size / 1024, 1),
            "preview": preview,
            "com_sua_voz": tipo == "diarizado" and transcricao_contem_voce(conteudo, rotulo),
        })
    return jsonify(resultado)


@app.route("/api/modelos")
def api_modelos():
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=5) as r:
            dados = json.loads(r.read())
        return jsonify([m["name"] for m in dados.get("models", [])])
    except Exception:
        return jsonify([])


@app.route("/api/chat", methods=["POST"])
def api_chat():
    cl = request.content_length or 0
    if cl > MAX_CORPO_CHAT_BYTES:
        return jsonify({"erro": "Corpo da requisição muito grande"}), 413

    dados = request.get_json(silent=True) or {}
    modelo = dados.get("modelo", "")
    nome = dados.get("transcricao", "")
    pergunta = dados.get("pergunta", "")
    historico = dados.get("historico", [])

    if not modelo:
        return jsonify({"erro": "Selecione um modelo Ollama na barra lateral."}), 400
    if isinstance(historico, list) and len(historico) > MAX_HISTORICO_CHAT:
        return jsonify({"erro": "Histórico excede o limite permitido"}), 400

    transcricao = ler_conteudo_transcricao(nome)
    if transcricao is None:
        return jsonify({"erro": "Acesso negado"}), 403

    return processar_chat(
        modelo,
        transcricao,
        pergunta,
        historico if isinstance(historico, list) else [],
        orcamento_fn=orcamento_chars,
        ctx_fn=consultar_context_length,
        sync_fn=_chamar_ollama_sync,
        max_chars=MAX_CHARS_TRANSCRICAO,
    )


def porta_livre(preferida=PORTAS_FALLBACK[0]):
    from config import PORTA_MEET_BRIDGE

    for porta in PORTAS_FALLBACK:
        if porta == PORTA_MEET_BRIDGE:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", porta))
                return porta
            except OSError:
                continue
    raise RuntimeError("Nenhuma porta livre encontrada para o assistente.")


if __name__ == "__main__":
    porta = porta_livre()
    print(f"Assistente rodando em http://localhost:{porta}")
    import webbrowser

    webbrowser.open(f"http://localhost:{porta}")
    app.run(host="127.0.0.1", port=porta, debug=False)
