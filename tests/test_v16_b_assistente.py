# -*- coding: utf-8 -*-
"""F11.B — Assistente layout+conteúdo (T-11.B1/B2/B3)."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from tests.front_assistente import CSS, HTML_TEMPLATE as HTML, JS  # v1.9: shell + módulos
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
    # UX-11.B1 → v1.9 (T-14.B3): ações rápidas viram chips de intenção montados a partir de intencoes.js
    assert "primario: true" in JS
    assert "Resumir reunião" in JS
    assert 'id="chips"' in HTML and 'id="chips-editar"' in HTML
    assert 'empty-tips' in HTML
    assert 'empty-icon' in HTML
    assert JS.count("rotulo: '") == 6


def test_html_tem_search_wrap_e_header_meta():
    assert 'search-wrap' in HTML
    assert 'search-icon' in HTML
    assert 'header-meta' in HTML
    assert 'id="statusbar"' in (REPO / 'templates' / 'base.html').read_text(encoding='utf-8')
    assert 'context-bar' in CSS
    assert '.tk-toast-region' in CSS  # v1.9: toasts tipados de ui.js


def test_js_busca_preserva_selecao():
    assert 'prev = selTrans.value' in JS
    assert 'items.some(x => x.arquivo === prev)' in JS
