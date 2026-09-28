# -*- coding: utf-8 -*-
"""UX-14.E3 — consentimento com DPI, ícone, fonte detectada e contagem visual (T-14.E3).

O que não pode mudar: `pedir_consentimento` continua fail-closed, o timeout e
os IDs de controle são os mesmos e `tests/test_aviso_gravacao.py` /
`tests/test_portao_consentimento.py` seguem verdes sem alteração.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import consentimento_gravacao
from consentimento_layout import (
    TEXTO_NAO,
    TEXTO_SIM,
    TITULO_PERGUNTA,
    descrever_fontes,
    layout_consentimento,
    texto_contagem,
)

RETANGULOS = ("icone", "titulo", "mensagem", "fonte_detectada", "progresso", "contagem", "botao_sim", "botao_nao", "dica")


def _retangulo(layout, nome):
    r = layout[nome]
    return (r["x"], r["y"], r["largura"], r["altura"])


@pytest.mark.parametrize("dpi", [96, 120, 144, 192])
def test_layout_escala_com_dpi(dpi):
    base = layout_consentimento(96)
    escalado = layout_consentimento(dpi)
    fator = dpi / 96
    assert escalado["escala"] == pytest.approx(fator)
    for nome in RETANGULOS:
        for valor_base, valor in zip(_retangulo(base, nome), _retangulo(escalado, nome)):
            assert isinstance(valor, int)
            assert valor == round(valor_base * fator), (nome, dpi)
    assert escalado["janela"]["largura"] == round(base["janela"]["largura"] * fator)
    assert escalado["janela"]["altura"] == round(base["janela"]["altura"] * fator)
    for chave, tamanho in base["fontes"].items():
        assert escalado["fontes"][chave] == round(tamanho * fator)


def test_layout_e_puro_e_nao_sobrepoe_controles():
    a, b = layout_consentimento(144), layout_consentimento(144)
    assert a == b and a is not b
    ordem = ("titulo", "mensagem", "fonte_detectada", "progresso", "contagem", "botao_sim", "dica")
    for anterior, seguinte in zip(ordem, ordem[1:]):
        fim = a[anterior]["y"] + a[anterior]["altura"]
        assert a[seguinte]["y"] >= fim, f"{seguinte} sobrepõe {anterior}"
    assert a["botao_nao"]["x"] >= a["botao_sim"]["x"] + a["botao_sim"]["largura"]
    for nome in RETANGULOS:
        assert a[nome]["x"] + a[nome]["largura"] <= a["janela"]["largura"], nome
        assert a[nome]["y"] + a[nome]["altura"] <= a["janela"]["altura"], nome


@pytest.mark.parametrize("dpi", [96, 120, 144, 192])
def test_botao_sim_altura_minima(dpi):
    from config import CONSENTIMENTO_BOTAO_ALTURA_MIN

    layout = layout_consentimento(dpi)
    minimo = round(CONSENTIMENTO_BOTAO_ALTURA_MIN * dpi / 96)
    assert layout["botao_sim"]["altura"] >= minimo >= 36 * dpi // 96
    assert layout["botao_sim"]["altura"] >= layout["botao_nao"]["altura"]
    assert layout["botao_sim"]["largura"] > layout["botao_nao"]["largura"], "primário tem mais peso visual"


def test_dpi_invalido_cai_em_96():
    assert layout_consentimento(0) == layout_consentimento(96)
    assert layout_consentimento(-10) == layout_consentimento(96)


def test_fontes_nunca_incluem_titulo_ou_nome():
    """A linha "Detectado:" só usa rótulos fixos por fonte do detector."""
    texto = descrever_fontes(["titulo", "Meet – abc-defg-hij", "Alice Silva", "extensao", "zoom", "microfone"])
    assert texto.startswith("Detectado: ")
    assert "abc-defg-hij" not in texto and "Alice" not in texto
    assert "Google Meet" in texto and "Zoom" in texto and "microfone" in texto
    assert texto.count("Google Meet") == 1
    assert descrever_fontes([]) == "Reunião detectada"
    assert descrever_fontes(["<script>"]) == "Reunião detectada"


def test_textos_do_dialogo():
    assert TITULO_PERGUNTA == "Gravar esta reunião?"
    assert TEXTO_SIM == "Gravar esta reunião" and TEXTO_NAO == "Não gravar"
    assert "30" in texto_contagem(30) and "sem gravar" in texto_contagem(30)
    assert consentimento_gravacao.layout_consentimento is layout_consentimento


def test_pedir_consentimento_aceita_fontes_e_continua_fail_closed(monkeypatch):
    assert "fontes" in inspect.signature(consentimento_gravacao.pedir_consentimento).parameters
    recebido = {}

    def falso(timeout_seg, fontes=()):
        recebido["fontes"] = tuple(fontes)
        raise OSError("indisponível")

    monkeypatch.setattr(consentimento_gravacao, "_mostrar_dialogo", falso)
    assert consentimento_gravacao.pedir_consentimento(timeout_seg=1, fontes=["titulo"]) is False
    assert recebido["fontes"] == ("titulo",)


def test_controles_novos_no_codigo_com_fallback():
    fonte = Path(consentimento_gravacao.__file__).read_text(encoding="utf-8")
    controles = Path(consentimento_gravacao.__file__).with_name("consentimento_controles.py").read_text(encoding="utf-8")
    assert "msctls_progress32" in controles and "LoadImageW" in controles
    assert "SetThreadDpiAwarenessContext" in controles
    # IDs e portas de saída iguais aos da v1.8
    assert "_ID_SIM = 1001" in fonte and "_ID_NAO = 1002" in fonte
    assert "resposta_autoriza_gravacao(" in fonte and "MessageBoxTimeoutW" not in fonte


def test_ciclo_passa_fontes_ativas_do_detector(modulo_transkriptor, monkeypatch):
    import app_bandeja_menu
    import app_ciclo_reuniao

    modulo = modulo_transkriptor
    monkeypatch.setattr(modulo, "chave_disponivel", lambda: False)
    monkeypatch.setattr(modulo, "perfil_existe", lambda *a, **k: False)
    monkeypatch.setattr(modulo, "_carregar_config_user", lambda: {})
    monkeypatch.setattr(modulo, "_atualizar_config_user", lambda **kv: None)
    monkeypatch.setattr(modulo, "sincronizar_token_extensao", lambda *a, **k: None)
    monkeypatch.setattr(modulo, "notificar", lambda *a, **k: None)
    monkeypatch.setattr(app_bandeja_menu, "notificar", lambda *a, **k: None)
    recebido = {}
    monkeypatch.setattr(app_ciclo_reuniao, "pedir_consentimento", lambda **kw: recebido.update(kw) or False)
    app = modulo.AppTranskriptor()
    app.detector = SimpleNamespace(reuniao_ativa=True, fontes_da_reuniao=["titulo", "microfone"])
    app._iniciar_transcricao = MagicMock()

    app._pedir_e_iniciar()

    assert recebido["fontes"] == ("titulo", "microfone")
    app._iniciar_transcricao.assert_not_called()
