# -*- coding: utf-8 -*-
"""UX-14.B1 — app shell da Central (T-14.B1): páginas, nav e abertura em janela de app."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def cliente():
    import assistente

    assistente.app.config["TESTING"] = True
    return assistente.app.test_client()


def test_assistente_renderiza_shell_com_seis_destinos(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert 'id="nav"' in html and 'id="statusbar"' in html and 'id="tema-toggle"' in html
    assert len(re.findall(r'class="tk-nav__item"', html)) == 6
    for pagina in ("inicio", "reunioes", "assistente", "participantes", "configuracoes", "diagnostico"):
        assert f'data-page="{pagina}"' in html
    assert html.count("Transkriptor</span>") == 1, "marca deve aparecer uma vez"
    assert not re.search(r"\sstyle\s*=", html)


def test_pagina_conhecida_sem_template_devolve_404_com_shell(cliente, monkeypatch):
    import central_paginas

    monkeypatch.setattr(central_paginas, "_template_existe", lambda _p: False)
    resposta = cliente.get("/reunioes")
    assert resposta.status_code == 404
    html = resposta.get_data(as_text=True)
    assert 'id="nav"' in html and "ainda não existe" in html


def test_slug_desconhecido_devolve_404_json(cliente):
    resposta = cliente.get("/reunioes-que-nao-existe")
    assert resposta.status_code == 404
    assert resposta.get_json()["erro"]


def test_pagina_fora_da_lista_nao_e_servida(cliente):
    assert cliente.get("/base").status_code == 404
    assert cliente.get("/indisponivel").status_code == 404
    assert cliente.get("/..%2Fassistente").status_code in (404, 400)


def test_abrir_navegador_prefere_janela_app(monkeypatch):
    import central_janela as flows

    chamadas = []
    monkeypatch.setattr(flows, "_executavel_navegador_app", lambda: r"C:\fake\msedge.exe")
    monkeypatch.setattr(flows.subprocess, "Popen", lambda args, **kw: chamadas.append(args))
    monkeypatch.setattr(flows.webbrowser, "open", lambda url: chamadas.append(("webbrowser", url)))
    flows._abrir_navegador("http://127.0.0.1:5050", "tok")
    assert chamadas == [[r"C:\fake\msedge.exe", "--app=http://127.0.0.1:5050?token=tok", "--window-size=1366,860"]]


def test_abrir_navegador_cai_para_webbrowser_sem_executavel(monkeypatch):
    import central_janela as flows

    chamadas = []
    monkeypatch.setattr(flows, "_executavel_navegador_app", lambda: None)
    monkeypatch.setattr(flows.webbrowser, "open", lambda url: chamadas.append(url))
    flows._abrir_navegador("http://127.0.0.1:5050", "tok")
    assert chamadas == ["http://127.0.0.1:5050?token=tok"]


def test_abrir_navegador_cai_para_webbrowser_se_popen_falha(monkeypatch):
    import central_janela as flows

    chamadas = []
    monkeypatch.setattr(flows, "_executavel_navegador_app", lambda: r"C:\fake\chrome.exe")

    def _falha(args, **kw):
        raise OSError("sem permissão")

    monkeypatch.setattr(flows.subprocess, "Popen", _falha)
    monkeypatch.setattr(flows.webbrowser, "open", lambda url: chamadas.append(url))
    flows._abrir_navegador("http://127.0.0.1:5050", "tok")
    assert chamadas == ["http://127.0.0.1:5050?token=tok"]


def test_janela_app_pode_ser_desligada(monkeypatch):
    import central_janela as flows

    monkeypatch.setenv("TRANSKRIPTOR_JANELA_APP", "0")
    assert flows._executavel_navegador_app() is None


def test_pagina_participantes_renderiza_painel(cliente):
    """UX-14.C1: a página Participantes serve o mesmo corpo do painel do assistente."""
    html = cliente.get("/participantes").get_data(as_text=True)
    for marcador in ('id="lista-falantes"', 'id="lista-participantes"', 'id="correcao-cluster"', 'id="reuniao-revisao"', "participantes--pagina"):
        assert marcador in html
    assert "FALANTE_" not in html
