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
    CHAT_MAX_CONCORRENTES,
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
app.config["MAX_CONTENT_LENGTH"] = MAX_CORPO_CHAT_BYTES

_semaforo_chat = threading.BoundedSemaphore(CHAT_MAX_CONCORRENTES)

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


@app.after_request
def cabecalhos_privacidade(resposta):
    resposta.headers["Cache-Control"] = "no-store"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    return resposta


@app.errorhandler(413)
def corpo_grande_demais(_erro):
    return jsonify({"erro": "Corpo da requisição muito grande"}), 413


@app.errorhandler(429)
def concorrencia_excedida(_erro):
    return jsonify({"erro": "Muitas requisições simultâneas"}), 429


def _extensao_transcricao_permitida(nome: str) -> bool:
    return nome.endswith(".txt") or nome.endswith(".tkpt")


_PADRAO_REUNIAO = None


def _reuniao_id_valido(meeting_id: str) -> bool:
    global _PADRAO_REUNIAO
    if _PADRAO_REUNIAO is None:
        import re as _re

        _PADRAO_REUNIAO = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
    return bool(_PADRAO_REUNIAO.fullmatch(str(meeting_id or "")))


def _pasta_resultados():
    from pathlib import Path as _Path

    pasta = _Path(PASTA_TRANSCRICOES) / "resultados"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _caminho_resultado(meeting_id: str):
    from pathlib import Path as _Path

    if not _reuniao_id_valido(meeting_id):
        return None
    caminho = (_pasta_resultados() / f"{meeting_id}.json").resolve()
    try:
        base = _pasta_resultados().resolve()
    except OSError:
        return None
    if caminho.parent != base:
        return None
    return caminho


@app.route("/api/reunioes")
def api_reunioes():
    return jsonify(sorted(p.stem for p in _pasta_resultados().glob("*.json")))


@app.route("/api/reunioes/<meeting_id>/resultado")
def api_resultado_reuniao(meeting_id: str):
    from resultado_reuniao import carregar_segmentos

    caminho = _caminho_resultado(meeting_id)
    if caminho is None or not caminho.is_file():
        return jsonify({"erro": "Reunião não encontrada"}), 404
    try:
        return jsonify(carregar_segmentos(caminho))
    except ValueError:
        return jsonify({"erro": "Resultado inválido"}), 422


@app.route("/api/reunioes/<meeting_id>/correcao", methods=["POST"])
def api_corrigir_reuniao(meeting_id: str):
    from renomear_falante_flow import corrigir_nome_reuniao

    if (request.content_length or 0) > MAX_CORPO_CHAT_BYTES:
        return jsonify({"erro": "Corpo da requisição muito grande"}), 413
    caminho = _caminho_resultado(meeting_id)
    if caminho is None or not caminho.is_file():
        return jsonify({"erro": "Reunião não encontrada"}), 404
    dados = request.get_json(silent=True) or {}
    try:
        revisao = corrigir_nome_reuniao(
            str(caminho),
            expected_revision=str(dados.get("expected_revision", "")),
            cluster_falante=str(dados.get("speaker_cluster_id", "")),
            novo_nome=str(dados.get("display_name", "")),
        )
    except ValueError as exc:
        codigo = 409 if "divergente" in str(exc) else 400
        return jsonify({"erro": str(exc)}), codigo
    return jsonify({"revision": revisao})


@app.route("/api/reunioes/<meeting_id>/desfazer", methods=["POST"])
def api_desfazer_reuniao(meeting_id: str):
    from resultado_reuniao import desfazer_correcao

    if (request.content_length or 0) > MAX_CORPO_CHAT_BYTES:
        return jsonify({"erro": "Corpo da requisição muito grande"}), 413
    caminho = _caminho_resultado(meeting_id)
    if caminho is None or not caminho.is_file():
        return jsonify({"erro": "Reunião não encontrada"}), 404
    dados = request.get_json(silent=True) or {}
    try:
        revisao = desfazer_correcao(
            caminho, expected_revision=str(dados.get("expected_revision", ""))
        )
    except ValueError as exc:
        codigo = 409 if "divergente" in str(exc) else 400
        return jsonify({"erro": str(exc)}), codigo
    return jsonify({"revision": revisao})


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
    from assistente_validacao import (
        PayloadInvalido,
        hosts_locais_aceitos,
        origem_permitida_chat,
        validar_chat_payload,
    )

    if not hosts_locais_aceitos(request.host):
        return jsonify({"erro": "Host não permitido"}), 403
    if not origem_permitida_chat(request.headers.get("Origin")):
        return jsonify({"erro": "Origem não permitida"}), 403
    try:
        pedido = validar_chat_payload(request.get_json(silent=True))
    except PayloadInvalido as exc:
        return jsonify({"erro": str(exc)}), 400
    modelo = pedido["modelo"]
    nome = pedido["transcricao"]
    pergunta = pedido["pergunta"]
    historico = [{"role": m.role, "content": m.content} for m in pedido["historico"]]

    transcricao = ler_conteudo_transcricao(nome)
    if transcricao is None:
        return jsonify({"erro": "Acesso negado"}), 403

    if not _semaforo_chat.acquire(blocking=False):
        return jsonify({"erro": "Muitas requisições simultâneas"}), 429
    try:
        return processar_chat(
            modelo,
            transcricao,
            pergunta,
            historico,
            orcamento_fn=orcamento_chars,
            ctx_fn=consultar_context_length,
            sync_fn=_chamar_ollama_sync,
            max_chars=MAX_CHARS_TRANSCRICAO,
        )
    finally:
        _semaforo_chat.release()


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
