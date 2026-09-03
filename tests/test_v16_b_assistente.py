# -*- coding: utf-8 -*-
"""F11.B — Assistente layout+conteúdo (T-11.B1/B2/B3)."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HTML = (REPO / "templates" / "assistente.html").read_text(encoding="utf-8")
CSS = (REPO / "static" / "assistente.css").read_text(encoding="utf-8")
JS = (REPO / "static" / "assistente.js").read_text(encoding="utf-8")
FRONT = HTML + "\n" + CSS + "\n" + JS


def test_html_tem_busca_e_context_bar():
    # FR-11.B1/B2
    assert 'id="busca-transcricao"' in HTML
    assert 'type="search"' in HTML
    assert 'id="context-bar"' in HTML
    assert 'id="context-file"' in HTML
    assert 'id="context-kb"' in HTML
    assert 'id="context-badge"' in HTML
    assert 'id="transcricao-count"' in HTML
    assert 'buscaInput' in JS
    assert 'filtrarTranscricoes' in JS
    assert 'renderTranscricoesSelect' in JS
    assert 'atualizarContextBar' in JS
    # Ctrl+K
    assert 'Ctrl+K' in JS or 'ctrlKey' in JS and 'buscaInput' in JS


def test_html_markdown_e_copiar():
    # FR-11.B3
    assert 'function renderMarkdown' in JS
    assert 'escapeHtml' in JS
    assert 'msg-copy' in JS
    assert 'msg-meta' in JS
    assert 'copiar-resposta' in HTML or 'copiar-resposta' in JS
    assert 'navigator.clipboard.writeText' in JS
    # Timer 15s ainda deve existir
    assert 'O modelo está pensando' in FRONT
    assert 'function iniciarTimer' in JS
    assert '15' in JS[JS.find('function iniciarTimer'):JS.find('function iniciarTimer')+600]


def test_html_action_cards_hierarquia():
    # UX-11.B1
    assert 'is-primary' in HTML
    assert 'Resumir reunião' in HTML
    assert 'action-desc' in HTML
    assert 'action-kbd' in HTML
    assert 'action-icon' in HTML
    # Empty tips
    assert 'empty-tips' in HTML
    assert 'empty-icon' in HTML
    # 6 cards
    assert HTML.count('class="action-card') == 6


def test_html_tem_search_wrap_e_header_meta():
    assert 'search-wrap' in HTML
    assert 'search-icon' in HTML
    assert 'header-meta' in HTML
    assert 'context-bar' in CSS
    assert '.toast-region' in CSS


def test_js_busca_preserva_selecao():
    assert 'prev = selTrans.value' in JS
    assert 'items.some(x => x.arquivo === prev)' in JS
