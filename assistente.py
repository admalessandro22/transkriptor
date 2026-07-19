# -*- coding: utf-8 -*-
"""
Assistente de reuniao - pagina web local que conversa com o Ollama.

Abre em http://localhost:5050 e permite:
- Selecionar uma transcrição salva (.txt ou _diarizado.txt)
- Ações rápidas: resumo, pontos principais, tarefas, decisões, próximos passos
- Chat livre para perguntar qualquer coisa sobre a reunião

Respostas em streaming direto do Ollama.
"""

import datetime
import json
import os
import secrets
import socket
import threading
import time
import urllib.request
from flask import Flask, Response, jsonify, request

from config import (
    BASE_DIR,
    PASTA_TRANSCRICOES,
    OLLAMA_URL,
    PORTAS_FALLBACK,
    MAX_HISTORICO_CHAT,
    MAX_CHARS_TRANSCRICAO,
    ROTULO_USUARIO,
)

app = Flask(__name__)

HEADER_TOKEN = "X-Transkriptor-Token"
SESSAO_TOKEN = os.environ.get("TRANSKRIPTOR_TOKEN") or secrets.token_urlsafe(32)
AVISO_TRUNCAGEM = "[AVISO: transcrição truncada por limite de tamanho]\n"


def obter_token_sessao():
    return SESSAO_TOKEN


def token_requisicao_valido() -> bool:
    """Aceita token no header ou query `?token=` (FR-6.1 / SEC-4)."""
    header = request.headers.get(HEADER_TOKEN)
    query = request.args.get("token")
    return header == SESSAO_TOKEN or query == SESSAO_TOKEN


@app.before_request
def verificar_token():
    if request.path.startswith("/api/"):
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


def transcricao_contem_voce(conteudo: str) -> bool:
    """True se diarização inclui o rótulo do usuário (FR-7.11)."""
    return ROTULO_USUARIO in conteudo


def ler_conteudo_transcricao(nome: str) -> str | None:
    """Único caminho de leitura de transcrições para a API (FR-3.4)."""
    caminho = caminho_transcricao_seguro(nome)
    if not caminho:
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


HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Transkriptor · Assistente de Reunião</title>
<style>
  :root {
    --bg-base: #0a0a0f;
    --bg-deep: #06060a;
    --panel: rgba(22, 22, 32, 0.55);
    --panel-solid: #11111b;
    --panel-hover: rgba(30, 30, 44, 0.7);
    --border: rgba(255, 255, 255, 0.10);
    --border-hover: rgba(255, 255, 255, 0.14);
    --text: #ece9e4;
    --text-2: #a8a29b;
    --text-3: #807a73;
    --violet: #8b5cf6;
    --indigo: #6366f1;
    --gold: #c9a961;
    --gold-bright: #e0c483;
    --grad-accent: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
    --grad-gold: linear-gradient(135deg, #e0c483 0%, #c9a961 100%);
    --shadow-sm: 0 2px 8px rgba(0,0,0,0.3);
    --shadow-lg: 0 12px 40px rgba(0,0,0,0.5);
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { height: 100%; overflow: hidden; }
  body {
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--bg-base);
    color: var(--text);
    display: flex;
    position: relative;
  }
  /* glows de fundo premium */
  body::before {
    content: ''; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
      radial-gradient(ellipse 600px 400px at 15% 20%, rgba(139,92,246,0.10), transparent 60%),
      radial-gradient(ellipse 500px 300px at 85% 80%, rgba(201,169,97,0.06), transparent 60%),
      radial-gradient(ellipse 800px 500px at 50% 100%, rgba(99,102,241,0.05), transparent 70%);
  }
  body::after {
    content: ''; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='4' height='4'%3E%3Crect width='4' height='4' fill='%23ffffff' fill-opacity='0.012'/%3E%3C/svg%3E");
  }

  /* ===== SIDEBAR ===== */
  .sidebar {
    width: 340px; min-width: 340px; height: 100vh; position: relative; z-index: 1;
    background: linear-gradient(180deg, rgba(14,14,22,0.95), rgba(8,8,14,0.98));
    border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
    backdrop-filter: blur(20px);
  }
  .brand {
    padding: 28px 26px 24px; display: flex; align-items: center; gap: 14px;
    border-bottom: 1px solid var(--border);
  }
  .brand-mark {
    width: 42px; height: 42px; border-radius: 12px; display: flex;
    align-items: center; justify-content: center; background: var(--grad-accent);
    box-shadow: 0 4px 16px rgba(139,92,246,0.4); flex-shrink: 0;
  }
  .brand-mark svg { width: 22px; height: 22px; fill: #fff; }
  .brand-text { display: flex; flex-direction: column; gap: 1px; }
  .brand-name { font-family: Georgia, "Times New Roman", serif; font-size: 19px; font-weight: 600; color: var(--gold-bright); letter-spacing: 0.5px; }
  .brand-sub { font-size: 11px; color: var(--text-3); letter-spacing: 1.5px; text-transform: uppercase; font-weight: 500; }

  .sidebar-body { flex: 1; overflow-y: auto; padding: 22px 22px 12px; }
  .sidebar-body::-webkit-scrollbar { width: 5px; }
  .sidebar-body::-webkit-scrollbar-thumb { background: var(--border-hover); border-radius: 4px; }

  .field-label {
    font-size: 10.5px; font-weight: 600; letter-spacing: 1.8px; text-transform: uppercase;
    color: var(--text-3); margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
  }
  .field-label::before { content: ''; width: 14px; height: 1px; background: var(--gold); opacity: 0.5; }
  .field { margin-bottom: 22px; }

  .select-wrap { position: relative; }
  .select-wrap::after {
    content: ''; position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
    width: 8px; height: 8px; border-right: 2px solid var(--text-2); border-bottom: 2px solid var(--text-2);
    transform: translateY(-65%) rotate(45deg); pointer-events: none;
  }
  select {
    width: 100%; background: var(--panel-solid); color: var(--text);
    border: 1px solid var(--border); border-radius: 10px; padding: 11px 36px 11px 14px;
    font-size: 13px; font-family: inherit; cursor: pointer; appearance: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  select:hover { border-color: var(--border-hover); }
  select:focus { outline: none; border-color: var(--violet); box-shadow: 0 0 0 3px rgba(139,92,246,0.15); }

  .actions-title { margin: 6px 0 14px; }

  .action-grid { display: flex; flex-direction: column; gap: 8px; }
  .action-card {
    display: flex; align-items: center; gap: 12px; padding: 12px 14px;
    background: var(--panel); border: 1px solid var(--border); border-radius: 11px;
    cursor: pointer; transition: all 0.2s ease; position: relative; overflow: hidden;
  }
  .action-card::before {
    content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: var(--grad-accent); transform: scaleY(0); transform-origin: center;
    transition: transform 0.25s ease;
  }
  .action-card:hover { background: var(--panel-hover); border-color: var(--border-hover); transform: translateX(2px); }
  .action-card:hover::before { transform: scaleY(1); }
  .action-icon { font-size: 18px; width: 28px; text-align: center; flex-shrink: 0; }
  .action-label { font-size: 13px; font-weight: 500; color: var(--text); }
  .action-card:active { transform: translateX(2px) scale(0.98); }

  .sidebar-footer {
    padding: 16px 26px; border-top: 1px solid var(--border);
    display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-3);
  }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--gold); box-shadow: 0 0 8px rgba(201,169,97,0.5); }
  .dot.off { background: #ef4444; box-shadow: 0 0 8px rgba(239,68,68,0.4); }

  /* ===== MAIN ===== */
  .main { flex: 1; display: flex; flex-direction: column; height: 100vh; position: relative; z-index: 1; min-width: 0; }

  #chat {
    flex: 1; overflow-y: auto; padding: 32px 48px; display: flex; flex-direction: column; gap: 20px;
  }
  #chat::-webkit-scrollbar { width: 6px; }
  #chat::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 4px; }
  #chat::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.15); }

  .msg-row { display: flex; gap: 14px; max-width: 820px; animation: fadeIn 0.4s ease; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  .msg-row.user { align-self: flex-end; flex-direction: row-reverse; }

  .avatar {
    width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center;
    justify-content: center; font-size: 15px; flex-shrink: 0; font-weight: 600;
  }
  .avatar.ai { background: var(--grad-accent); box-shadow: 0 4px 14px rgba(139,92,246,0.3); }
  .avatar.user { background: var(--grad-gold); box-shadow: 0 4px 14px rgba(201,169,97,0.3); color: #1a1a1a; }

  .bubble {
    padding: 14px 18px; border-radius: 16px; line-height: 1.7; font-size: 14px;
    white-space: pre-wrap; word-wrap: break-word; min-width: 0;
  }
  .msg-row.ai .bubble {
    background: var(--panel); border: 1px solid var(--border);
    border-top-left-radius: 5px; backdrop-filter: blur(8px);
  }
  .msg-row.user .bubble {
    background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(99,102,241,0.1));
    border: 1px solid rgba(139,92,246,0.25); border-top-right-radius: 5px;
  }

  .typing { display: flex; gap: 4px; padding: 4px 0; }
  .typing span { width: 7px; height: 7px; border-radius: 50%; background: var(--text-3); animation: bounce 1.2s infinite; }
  .typing span:nth-child(2) { animation-delay: 0.2s; }
  .typing span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce { 0%,60%,100% { transform: translateY(0); opacity: 0.4; } 30% { transform: translateY(-6px); opacity: 1; } }

  .empty-state {
    margin: auto; text-align: center; max-width: 420px; padding: 40px;
  }
  .empty-icon {
    width: 72px; height: 72px; margin: 0 auto 20px; border-radius: 20px;
    background: var(--grad-accent); display: flex; align-items: center; justify-content: center;
    box-shadow: 0 12px 40px rgba(139,92,246,0.35);
  }
  .empty-icon svg { width: 34px; height: 34px; fill: #fff; }
  .empty-title { font-family: Georgia, "Times New Roman", serif; font-size: 24px; font-weight: 500; color: var(--text); margin-bottom: 8px; }
  .empty-desc { font-size: 14px; color: var(--text-2); line-height: 1.7; }

  /* ===== INPUT ===== */
  .input-area {
    padding: 18px 48px 24px; position: relative;
  }
  .input-wrap {
    display: flex; gap: 12px; align-items: flex-end;
    background: var(--panel-solid); border: 1px solid var(--border);
    border-radius: 16px; padding: 10px 10px 10px 18px;
    transition: border-color 0.2s, box-shadow 0.2s;
    box-shadow: var(--shadow-lg);
  }
  .input-wrap:focus-within { border-color: rgba(139,92,246,0.4); box-shadow: 0 0 0 3px rgba(139,92,246,0.12), var(--shadow-lg); }
  #input {
    flex: 1; background: transparent; border: none; color: var(--text);
    font-size: 14px; font-family: inherit; resize: none; height: 26px; max-height: 140px;
    line-height: 1.5; padding: 4px 0;
  }
  #input::placeholder { color: var(--text-3); }
  #input:focus { outline: none; }
  #send {
    width: 42px; height: 42px; border: none; border-radius: 12px; cursor: pointer;
    background: var(--grad-accent); display: flex; align-items: center; justify-content: center;
    transition: transform 0.15s, box-shadow 0.2s; flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(139,92,246,0.35);
  }
  #send:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(139,92,246,0.5); }
  #send:active { transform: scale(0.92); }
  #send:disabled { opacity: 0.4; cursor: not-allowed; transform: none; box-shadow: none; }
  #send svg { width: 18px; height: 18px; fill: #fff; }

  .input-hint { font-size: 11px; color: var(--text-3); text-align: center; margin-top: 8px; }
  kbd { background: var(--panel-solid); border: 1px solid var(--border); border-radius: 4px; padding: 1px 5px; font-size: 10px; }

  /* UX-06: focus-visible para acessibilidade */
  .action-card:focus-visible, select:focus-visible,
  #send:focus-visible, #input:focus-visible, #stop:focus-visible, #limpar:focus-visible {
    outline: 2px solid var(--gold-bright);
    outline-offset: 2px;
  }

  /* UX-05: botão parar + cronômetro */
  #stop {
    width: 42px; height: 42px; border: none; border-radius: 12px; cursor: pointer;
    background: #ef4444; display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; transition: transform 0.15s, box-shadow 0.2s;
    box-shadow: 0 4px 14px rgba(239,68,68,0.35);
  }
  #stop:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(239,68,68,0.5); }
  #stop:active { transform: scale(0.92); }
  #stop svg { width: 16px; height: 16px; fill: #fff; }

  #limpar {
    background: transparent; border: 1px solid var(--border); color: var(--text-2);
    padding: 6px 12px; border-radius: 8px; cursor: pointer; font-size: 12px;
    font-family: inherit; transition: all 0.15s;
  }
  #limpar:hover { border-color: var(--border-hover); color: var(--text); }

  .timer { font-size: 11px; color: var(--text-3); margin-top: 6px; text-align: center; }
  .timer.longo { color: var(--gold-bright); }

  .progress-bar {
    height: 3px; margin-top: 8px; border-radius: 2px; overflow: hidden;
    background: var(--border); display: none;
  }
  .progress-bar.visible { display: block; }
  .progress-bar::after {
    content: ''; display: block; height: 100%; width: 40%;
    background: var(--grad-accent);
    animation: progress-indeterminate 1.2s ease-in-out infinite;
  }
  @keyframes progress-indeterminate {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(350%); }
  }

  .transcricao-meta {
    font-size: 11px; color: var(--text-3); margin-top: 6px; min-height: 16px;
  }

  #copiar-resposta {
    background: transparent; border: 1px solid var(--border); color: var(--text-2);
    padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 11px;
    font-family: inherit; margin-left: 8px; transition: all 0.15s;
  }
  #copiar-resposta:hover { border-color: var(--border-hover); color: var(--text); }
  #copiar-resposta:disabled { opacity: 0.35; cursor: not-allowed; }

  .main-header {
    display: none; align-items: center; gap: 12px; padding: 14px 20px 0;
  }
  #menu-toggle {
    width: 40px; height: 40px; border: 1px solid var(--border); border-radius: 10px;
    background: var(--panel-solid); color: var(--text); font-size: 20px; cursor: pointer;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }
  #menu-toggle:hover { border-color: var(--border-hover); }
  .drawer-overlay {
    display: none; position: fixed; inset: 0; z-index: 40;
    background: rgba(0,0,0,0.55); backdrop-filter: blur(2px);
  }
  .drawer-overlay.open { display: block; }

  /* UX-03: badge de tipo na transcrição */
  .badge-tipo {
    display: inline-block; font-size: 9px; font-weight: 600; padding: 1px 6px;
    border-radius: 4px; margin-left: 6px; vertical-align: middle;
    background: rgba(139,92,246,0.2); color: var(--violet);
  }
  .badge-tipo.diarizado { background: rgba(201,169,97,0.2); color: var(--gold-bright); }
  .badge-voce { color: var(--gold-bright); font-weight: 600; }

  @media (max-width: 820px) {
    #chat { padding: 24px 20px; }
    .input-area { padding: 14px 20px 20px; }
  }
  @media (max-width: 375px) {
    .main-header { display: flex; }
    .sidebar {
      position: fixed; left: 0; top: 0; z-index: 50;
      transform: translateX(-100%); transition: transform 0.25s ease;
      box-shadow: var(--shadow-lg);
    }
    .sidebar.drawer-open { transform: translateX(0); }
    #chat { padding: 16px 14px; }
    .input-area { padding: 12px 14px 16px; }
  }
</style>
</head>
<body>
  <div class="drawer-overlay" id="drawer-overlay" aria-hidden="true"></div>
  <aside class="sidebar" id="sidebar">
    <div class="brand">
      <div class="brand-mark">
        <svg viewBox="0 0 24 24"><path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3zm7 9a7 7 0 0 1-14 0H3a9 9 0 0 0 8 8.94V23h2v-3.06A9 9 0 0 0 21 11h-2z"/></svg>
      </div>
      <div class="brand-text">
        <span class="brand-name">Transkriptor</span>
        <span class="brand-sub">Assistente de Reunião</span>
      </div>
    </div>
    <div class="sidebar-body">
      <div class="field">
        <label class="field-label" for="transcricao" id="lbl-transcricao">Transcrição</label>
        <div class="select-wrap"><select id="transcricao" aria-labelledby="lbl-transcricao" title="Transcrição"><option value="">Carregando...</option></select></div>
        <div class="transcricao-meta" id="tamanho-kb" aria-live="polite"></div>
      </div>
      <div class="field">
        <label class="field-label" for="modelo" id="lbl-modelo">Modelo IA</label>
        <div class="select-wrap"><select id="modelo" aria-labelledby="lbl-modelo" title="Modelo Ollama"></select></div>
      </div>
      <div class="field">
        <div class="field-label actions-title">Ações Rápidas</div>
        <div class="action-grid" role="group" aria-label="Ações rápidas de análise">
          <button type="button" class="action-card" data-prompt="Atue como um analista de reuniões sênior. Elabore um resumo executivo estruturado desta reunião contendo: (1) um parágrafo de contexto sobre o propósito do encontro, (2) os temas centrais discutidos organizados por ordem de relevância, com uma breve descrição de cada um, e (3) uma conclusão com o desfecho geral. Use linguagem objetiva e profissional." aria-label="Resumir reunião"><span class="action-icon" aria-hidden="true">📝</span><span class="action-label">Resumir reunião</span></button>
          <button type="button" class="action-card" data-prompt="Atue como um analista de reuniões sênior. Extraia e liste os pontos principais discutidos nesta reunião. Para cada ponto, apresente: (1) um título curto e descritivo, (2) um resumo do que foi dito sobre o tema e (3) os participantes envolvidos na discussão (se identificáveis). Organize por ordem de importância e impacto. Formate em lista numerada." aria-label="Listar pontos principais"><span class="action-icon" aria-hidden="true">🎯</span><span class="action-label">Pontos principais</span></button>
          <button type="button" class="action-card" data-prompt="Atue como um project manager. Identifique todas as tarefas, ações e responsabilidades mencionadas nesta reunião. Para cada item, apresente uma tabela ou lista estruturada com: (1) a tarefa/ação a ser realizada, (2) o responsável atribuído (se mencionado), (3) o prazo ou data limite (se definido), (4) o nível de prioridade (Alta/Média/Baixa) inferido pelo contexto e (5) eventuais dependências de outras tarefas. Se uma informação não foi explicitada, marque como 'a definir'. Destaque as tarefas críticas em primeiro lugar." aria-label="Listar tarefas e ações"><span class="action-icon" aria-hidden="true">✅</span><span class="action-label">Tarefas e ações</span></button>
          <button type="button" class="action-card" data-prompt="Atue como um analista de negócios. Identifique e liste todas as decisões tomadas durante esta reunião. Para cada decisão, apresente: (1) a decisão em si de forma clara, (2) o contexto ou problema que motivou a decisão, (3) quem propôs ou defendeu a decisão (se identificável) e (4) o impacto esperado dessa decisão. Caso existam decisões que foram apenas parcialmente acordadas ou que ainda dependam de validação posterior, destaque-as separadamente como 'decisões pendentes de confirmação'." aria-label="Listar decisões tomadas"><span class="action-icon" aria-hidden="true">⚖️</span><span class="action-label">Decisões</span></button>
          <button type="button" class="action-card" data-prompt="Atue como um project manager. Extraia e organize os próximos passos definidos nesta reunião em um plano de ação claro e acionável. Para cada item, inclua: (1) a ação concreta a ser executada, (2) o responsável (se mencionado), (3) o prazo (se definido), (4) o critério de conclusão esperado e (5) a prioridade (Alta/Média/Baixa). Agrupe as ações por prazo (curto prazo / médio prazo / longo prazo). Inclua também qualquer reunião de acompanhamento mencionada." aria-label="Listar próximos passos"><span class="action-icon" aria-hidden="true">🔜</span><span class="action-label">Próximos passos</span></button>
          <button type="button" class="action-card" data-prompt="Atue como um consultor de riscos. Identifique todos os itens que ficaram em aberto, pendentes ou sem resolução nesta reunião. Classifique cada item como: Dúvida (pergunta sem resposta), Risco (potencial problema identificado) ou Pendência (ação que depende de algo externo). Para cada um, apresente: (1) a descrição do item, (2) o tipo de classificação, (3) o nível de criticidade (Alto/Médio/Baixo), (4) quem precisa responder ou resolver (se aplicável) e (5) uma sugestão de mitigação ou próximo passo para encerrar o item." aria-label="Listar pendências e riscos"><span class="action-icon" aria-hidden="true">⚠️</span><span class="action-label">Pendências e riscos</span></button>
        </div>
      </div>
    </div>
    <div class="sidebar-footer">
      <span class="dot" id="ollama-dot"></span>
      <span id="status-modelo">Conectando ao Ollama...</span>
    </div>
  </aside>

  <main class="main">
    <div class="main-header">
      <button type="button" id="menu-toggle" aria-label="Abrir menu" aria-expanded="false" aria-controls="sidebar">☰</button>
      <span class="brand-name" style="font-family:Georgia,'Times New Roman',serif;font-size:17px;color:var(--gold-bright)">Transkriptor</span>
    </div>
    <div id="chat" role="log" aria-live="polite" aria-label="Histórico da conversa">
      <div class="empty-state" id="empty" role="status">
        <div class="empty-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
        </div>
        <div class="empty-title">Como posso ajudar?</div>
        <div class="empty-desc">Selecione uma transcrição na barra lateral e faça uma pergunta sobre a reunião, ou use uma das ações rápidas.</div>
      </div>
    </div>
    <div class="input-area">
      <div class="input-wrap">
        <textarea id="input" placeholder="Pergunte algo sobre a reunião..." rows="1" aria-label="Campo de pergunta"></textarea>
        <button id="send" title="Enviar" aria-label="Enviar pergunta">
          <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
        </button>
        <button id="stop" title="Parar" aria-label="Parar geração" style="display:none">
          <svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
        </button>
      </div>
      <div class="input-hint"><kbd>Enter</kbd> para enviar · <kbd>Shift</kbd>+<kbd>Enter</kbd> para nova linha · <button id="limpar" aria-label="Limpar conversa">Limpar conversa</button> · <button type="button" id="copiar-resposta" aria-label="Copiar última resposta da IA" disabled>Copiar resposta</button></div>
      <div class="progress-bar" id="progress-bar" aria-hidden="true"></div>
      <div class="timer" id="timer" style="display:none"></div>
    </div>
  </main>

<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const stopBtn = document.getElementById('stop');
const limparBtn = document.getElementById('limpar');
const selTrans = document.getElementById('transcricao');
const selMod = document.getElementById('modelo');
const emptyEl = document.getElementById('empty');
const ollamaDot = document.getElementById('ollama-dot');
const statusMod = document.getElementById('status-modelo');
const timerEl = document.getElementById('timer');
const progressBar = document.getElementById('progress-bar');
const tamanhoKbEl = document.getElementById('tamanho-kb');
const copiarBtn = document.getElementById('copiar-resposta');
const menuToggle = document.getElementById('menu-toggle');
const sidebarEl = document.getElementById('sidebar');
const drawerOverlay = document.getElementById('drawer-overlay');
let busy = false;
let abortController = null;
let timerInterval = null;
let timerStart = 0;
let historico = [];  // T4.2: histórico de conversa (UX-04)
let transcricoesLista = [];
let ultimaRespostaIA = '';
const API_TOKEN = new URLSearchParams(window.location.search).get('token') || '';
function apiHeaders(extra = {}) {
  return Object.assign({'X-Transkriptor-Token': API_TOKEN}, extra);
}

function atualizarTamanhoKb() {
  const item = transcricoesLista.find(t => t.arquivo === selTrans.value);
  if (!item) {
    tamanhoKbEl.textContent = '';
    return;
  }
  let meta = `${item.tamanho_kb} KB`;
  if (item.com_sua_voz) meta += ' · com sua voz';
  tamanhoKbEl.innerHTML = item.com_sua_voz
    ? `${item.tamanho_kb} KB · <span class="badge-voce">com sua voz</span>`
    : meta;
}

function buildModelOptions(modelos) {
  selMod.replaceChildren();
  if (!modelos.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'Ollama offline';
    selMod.appendChild(opt);
    statusMod.textContent = 'Ollama offline';
    ollamaDot.classList.add('off');
    return;
  }
  for (const nome of modelos) {
    const opt = document.createElement('option');
    opt.value = nome;
    opt.textContent = nome;
    selMod.appendChild(opt);
  }
  statusMod.textContent = modelos[0];
  ollamaDot.classList.remove('off');
}

function buildSelectOptions(items) {
  transcricoesLista = items;
  selTrans.replaceChildren();
  if (!items.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '(nenhuma transcrição)';
    selTrans.appendChild(opt);
    tamanhoKbEl.textContent = '';
    return;
  }
  for (const t of items) {
    const opt = document.createElement('option');
    opt.value = t.arquivo;
    let sufixo = t.tipo === 'diarizado' ? ' [vozes]' : ' [texto]';
    if (t.com_sua_voz) sufixo += ' · com sua voz';
    opt.textContent = `${t.data} — ${t.preview || '(vazio)'}${sufixo}`;
    selTrans.appendChild(opt);
  }
  atualizarTamanhoKb();
}

async function loadList() {
  try {
    const r = await fetch('/api/transcricoes', {headers: apiHeaders()}); const d = await r.json();
    buildSelectOptions(d);
  } catch(e) {
    selTrans.replaceChildren();
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'erro ao carregar';
    selTrans.appendChild(opt);
  }
  try {
    const r = await fetch('/api/modelos', {headers: apiHeaders()}); const d = await r.json();
    buildModelOptions(d);
  } catch(e) { buildModelOptions([]); }
}
selMod.addEventListener('change', ()=>{ statusMod.textContent = selMod.value; });

function addMsg(role, text) {
  if (emptyEl) emptyEl.remove();
  const row = document.createElement('div');
  row.className = 'msg-row '+role;
  const av = document.createElement('div');
  av.className = 'avatar '+role;
  av.setAttribute('aria-hidden', 'true');
  av.innerHTML = role==='ai' ? '<svg viewBox="0 0 24 24" style="width:18px;height:18px;fill:#fff"><path d="M12 2L2 7l10 5 10-5-10-5zm0 7L2 14l10 5 10-5-10-5z"/></svg>' : 'Você';
  const bub = document.createElement('div');
  bub.className = 'bubble'; bub.textContent = text;
  row.appendChild(av); row.appendChild(bub);
  chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
  return bub;
}

function addTyping() {
  if (emptyEl) emptyEl.remove();
  const row = document.createElement('div');
  row.className = 'msg-row ai'; row.id = 'typing-row';
  const av = document.createElement('div'); av.className = 'avatar ai';
  av.setAttribute('aria-hidden', 'true');
  av.innerHTML = '<svg viewBox="0 0 24 24" style="width:18px;height:18px;fill:#fff"><path d="M12 2L2 7l10 5 10-5-10-5zm0 7L2 14l10 5 10-5-10-5z"/></svg>';
  const bub = document.createElement('div'); bub.className = 'bubble';
  bub.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
  row.appendChild(av); row.appendChild(bub);
  chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
  return bub;
}

function iniciarTimer() {
  timerStart = Date.now();
  timerEl.style.display = 'block';
  timerEl.classList.remove('longo');
  timerEl.textContent = 'Processando... 0s';
  timerInterval = setInterval(() => {
    const seg = Math.floor((Date.now() - timerStart) / 1000);
    if (seg >= 15) {
      timerEl.classList.add('longo');
      timerEl.textContent = 'O modelo está pensando... (' + seg + 's)';
    } else {
      timerEl.textContent = `Processando... ${seg}s`;
    }
  }, 1000);
}

function pararTimer() {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  timerEl.style.display = 'none';
  timerEl.classList.remove('longo');
}

function mostrarBotoes(ocupado) {
  sendBtn.style.display = ocupado ? 'none' : 'flex';
  stopBtn.style.display = ocupado ? 'flex' : 'none';
  progressBar.classList.toggle('visible', ocupado);
  progressBar.setAttribute('aria-hidden', ocupado ? 'false' : 'true');
}

async function pergunta(prompt) {
  const transc = selTrans.value;
  const modelo = selMod.value;
  if (!transc) { mostrarToastInline('Selecione uma transcrição primeiro.'); return; }
  if (!modelo || busy) return;
  busy = true; mostrarBotoes(true);
  addMsg('user', prompt);
  const aiEl = addTyping();
  iniciarTimer();
  let firstToken = true;
  abortController = new AbortController();
  try {
    const res = await fetch('/api/chat', {method:'POST', headers:apiHeaders({'Content-Type':'application/json'}),
      body: JSON.stringify({modelo, transcricao:transc, pergunta:prompt, historico}),
      signal: abortController.signal});
    const reader = res.body.getReader(); const dec = new TextDecoder(); let txt='';
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      txt += dec.decode(value, {stream:true});
      if (firstToken) { aiEl.innerHTML = ''; firstToken = false; pararTimer(); }
      aiEl.textContent = txt; chat.scrollTop = chat.scrollHeight;
    }
    if (firstToken) { aiEl.textContent = '(sem resposta)'; pararTimer(); }
    if (!txt.trim()) aiEl.textContent = '(sem resposta)';
    if (txt.trim()) {
      ultimaRespostaIA = txt;
      copiarBtn.disabled = false;
    }
    historico.push({role:'user', content:prompt});
    if (txt.trim()) historico.push({role:'assistant', content:txt});
  } catch(e) {
    pararTimer();
    if (e.name === 'AbortError') { aiEl.textContent = '(cancelado)'; }
    else { aiEl.textContent = 'Erro: '+e.message; }
  } finally {
    busy = false; mostrarBotoes(false); abortController = null; pararTimer();
  }
}

function mostrarToastInline(msg) {
  if (emptyEl) emptyEl.remove();
  const el = document.createElement('div');
  el.className = 'msg-row ai';
  el.innerHTML = '<div class="avatar ai" aria-hidden="true"><svg viewBox="0 0 24 24" style="width:18px;height:18px;fill:#fff"><path d="M12 2L2 7l10 5 10-5-10-5zm0 7L2 14l10 5 10-5-10-5z"/></svg></div><div class="bubble" style="color:var(--gold-bright)">' + msg + '</div>';
  chat.appendChild(el); chat.scrollTop = chat.scrollHeight;
}

function abrirDrawer(aberto) {
  sidebarEl.classList.toggle('drawer-open', aberto);
  drawerOverlay.classList.toggle('open', aberto);
  menuToggle.setAttribute('aria-expanded', aberto ? 'true' : 'false');
  drawerOverlay.setAttribute('aria-hidden', aberto ? 'false' : 'true');
}

function copiarUltimaResposta() {
  if (!ultimaRespostaIA) return;
  navigator.clipboard.writeText(ultimaRespostaIA).then(() => {
    const prev = copiarBtn.textContent;
    copiarBtn.textContent = 'Copiado!';
    setTimeout(() => { copiarBtn.textContent = prev; }, 1500);
  }).catch(() => {
    copiarBtn.textContent = 'Erro ao copiar';
    setTimeout(() => { copiarBtn.textContent = 'Copiar resposta'; }, 1500);
  });
}

function navegarActionCards(e) {
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
  const alvo = e.target;
  if (alvo && /^(TEXTAREA|INPUT|SELECT)$/i.test(alvo.tagName)) return;
  const cards = [...document.querySelectorAll('.action-card')];
  if (!cards.length) return;
  const idx = cards.indexOf(document.activeElement);
  if (idx === -1) return;
  if (e.key === 'ArrowDown' && idx < cards.length - 1) cards[idx + 1].focus();
  if (e.key === 'ArrowUp' && idx > 0) cards[idx - 1].focus();
  e.preventDefault();
}

function limparConversa() {
  historico = [];
  ultimaRespostaIA = '';
  copiarBtn.disabled = true;
  chat.innerHTML = '';
  const empty = document.createElement('div');
  empty.className = 'empty-state'; empty.id = 'empty'; empty.setAttribute('role', 'status');
  empty.innerHTML = '<div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24" style="width:34px;height:34px;fill:#fff"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg></div><div class="empty-title">Como posso ajudar?</div><div class="empty-desc">Selecione uma transcrição na barra lateral e faça uma pergunta sobre a reunião, ou use uma das ações rápidas.</div>';
  chat.appendChild(empty);
  input.focus();
}

sendBtn.onclick = ()=>{ const t = input.value.trim(); if (!t) return; input.value=''; input.style.height='auto'; pergunta(t); };
stopBtn.onclick = ()=>{ if (abortController) abortController.abort(); };
limparBtn.onclick = limparConversa;
copiarBtn.onclick = copiarUltimaResposta;
menuToggle.onclick = ()=> abrirDrawer(!sidebarEl.classList.contains('drawer-open'));
drawerOverlay.onclick = ()=> abrirDrawer(false);
selTrans.addEventListener('change', atualizarTamanhoKb);
input.addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendBtn.click(); }});
input.addEventListener('input', ()=>{ input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,140)+'px'; });
document.addEventListener('keydown', navegarActionCards);
document.querySelectorAll('.action-card').forEach(b=>{
  b.onclick = ()=>pergunta(b.dataset.prompt);
});
// UX-06: foco automático no textarea
input.focus();
loadList();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML


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
    for nome in arquivos:
        caminho = os.path.join(PASTA_TRANSCRICOES, nome)
        stat = os.stat(caminho)
        preview = ""
        conteudo = ""
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
        com_sua_voz = tipo == "diarizado" and transcricao_contem_voce(conteudo)
        resultado.append({
            "arquivo": nome,
            "data": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
            "tipo": tipo,
            "tamanho_kb": round(stat.st_size / 1024, 1),
            "preview": preview,
            "com_sua_voz": com_sua_voz,
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
    dados = request.json
    modelo = dados.get("modelo", "")
    nome = dados.get("transcricao", "")
    pergunta = dados.get("pergunta", "")
    historico = dados.get("historico", [])

    if not modelo:
        return jsonify({"erro": "Selecione um modelo Ollama na barra lateral."}), 400

    transcricao = ler_conteudo_transcricao(nome)
    if transcricao is None:
        return jsonify({"erro": "Acesso negado"}), 403

    truncada = len(transcricao) > MAX_CHARS_TRANSCRICAO
    if truncada:
        transcricao = transcricao[:MAX_CHARS_TRANSCRICAO]

    system = (
        "Você é um assistente especializado em analisar reuniões. "
        "Use a transcrição abaixo como contexto para responder às perguntas do usuário. "
        "Responda sempre em português, de forma clara e organizada. "
        "Se a informação não estiver na transcrição, diga que não há dados suficientes.\n\n"
        f"=== TRANSCRIÇÃO ===\n{transcricao}\n=== FIM ==="
    )

    # T4.1: inclui histórico de conversa (truncado em MAX_HISTORICO_CHAT)
    mensagens = [{"role": "system", "content": system}]
    for msg in historico[-MAX_HISTORICO_CHAT:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            mensagens.append({"role": msg["role"], "content": msg["content"]})
    mensagens.append({"role": "user", "content": pergunta})

    payload = json.dumps({
        "model": modelo,
        "messages": mensagens,
        "stream": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    def stream():
        if truncada:
            yield AVISO_TRUNCAGEM
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for linha in resp:
                    linha = linha.decode("utf-8").strip()
                    if not linha:
                        continue
                    try:
                        bloco = json.loads(linha)
                        conteudo = bloco.get("message", {}).get("content", "")
                        if conteudo:
                            yield conteudo
                        if bloco.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            yield f"\n[Erro ao contatar o Ollama: {e}]"

    headers = {"X-Transkriptor-Truncada": "true"} if truncada else {}
    return Response(stream(), mimetype="text/plain; charset=utf-8", headers=headers)


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
