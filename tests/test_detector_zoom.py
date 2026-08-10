# -*- coding: utf-8 -*-
"""FR-10.A3 — reunião do Zoom detectada sem depender do idioma do título.

O Zoom era visto só pelo texto da janela, e o texto muda: `Zoom Meeting` em
inglês, `Reunião Zoom` em português, e nas versões 6.x a chamada pode acontecer
dentro da janela chamada `Zoom Workplace`. Se o texto não casasse, o produto
ficava cego — `zoom.exe` podia estar com o microfone aberto que nada iniciava,
porque microfone sozinho é sinal auxiliar (FR-10.A1).

Duas rotas independentes, ambas fortes:

* **classe da janela** — o Windows nomeia a janela de chamada do Zoom com uma
  classe própria, que não muda com idioma nem com rebranding;
* **microfone + janela do Zoom** — `zoom.exe` só segura o microfone em chamada;
  exigir também uma janela do Zoom evita confundir com o teste de áudio de
  outro app.
"""
from __future__ import annotations

import pytest

from detector_zoom import (
    CLASSES_REUNIAO_ZOOM,
    Janela,
    janela_e_do_zoom,
    zoom_em_reuniao,
)


def _janela(titulo="", classe="", visivel=True):
    return Janela(titulo=titulo, classe=classe, visivel=visivel)


# --- rota 1: classe da janela ------------------------------------------------


@pytest.mark.parametrize("classe", CLASSES_REUNIAO_ZOOM)
def test_classe_de_janela_de_chamada_e_reuniao(classe):
    """Independe do texto: a janela pode se chamar qualquer coisa."""
    janelas = [_janela(titulo="Zoom Workplace", classe=classe)]

    ativo, motivo = zoom_em_reuniao(janelas, [])

    assert ativo is True
    assert motivo == "classe da janela do Zoom"


def test_janela_ociosa_do_zoom_nao_e_reuniao():
    """`Zoom Workplace` parado não pode abrir gravação."""
    janelas = [_janela(titulo="Zoom Workplace", classe="ZPFTEWndClass")]

    assert zoom_em_reuniao(janelas, []) == (False, "")


# --- rota 2: microfone corroborado pela janela -------------------------------


def test_microfone_do_zoom_com_janela_do_zoom_e_reuniao():
    janelas = [_janela(titulo="Zoom Workplace", classe="ZPFTEWndClass")]

    ativo, motivo = zoom_em_reuniao(janelas, ["zoom.exe"])

    assert ativo is True
    assert motivo == "microfone do Zoom com janela aberta"


def test_microfone_do_zoom_sem_janela_do_zoom_nao_inicia():
    """FR-10.A1: microfone isolado continua não iniciando reunião."""
    janelas = [_janela(titulo="Documento - Word", classe="OpusApp")]

    assert zoom_em_reuniao(janelas, ["zoom.exe"]) == (False, "")


def test_microfone_de_outro_app_nao_conta_para_o_zoom():
    janelas = [_janela(titulo="Zoom Workplace", classe="ZPFTEWndClass")]

    assert zoom_em_reuniao(janelas, ["chrome.exe"]) == (False, "")


def test_sem_zoom_nenhum_sinal():
    assert zoom_em_reuniao([], []) == (False, "")


# --- reconhecimento de janela do Zoom ---------------------------------------


@pytest.mark.parametrize(
    "titulo,classe",
    [
        ("Zoom Workplace", ""),
        ("Zoom", ""),
        ("Reunião Zoom", ""),
        ("Reunião do Zoom", ""),
        ("", "ZPFTEWndClass"),
        ("", "ZPContentViewWndClass"),
    ],
)
def test_reconhece_janela_do_zoom(titulo, classe):
    assert janela_e_do_zoom(_janela(titulo=titulo, classe=classe)) is True


@pytest.mark.parametrize(
    "titulo,classe",
    [
        ("Documento - Word", "OpusApp"),
        ("Zoombie Survival - Google Chrome", "Chrome_WidgetWin_1"),
        ("", ""),
        # Casos vistos numa varredura real de 354 janelas: só mencionar "zoom"
        # não faz de uma janela qualquer uma janela do Zoom.
        ("Diagnosticar problemas em Meet e Zoom", "CASCADIA_HOSTING_WINDOW_CLASS"),
        ("Ata da reunião do Zoom de ontem.docx - Word", "OpusApp"),
        ("Como usar o Zoom - Google Chrome", "Chrome_WidgetWin_1"),
    ],
)
def test_nao_confunde_outras_janelas_com_zoom(titulo, classe):
    assert janela_e_do_zoom(_janela(titulo=titulo, classe=classe)) is False


def test_varredura_real_nao_ve_zoom_onde_nao_ha():
    """Roda contra as janelas de verdade desta máquina — sem Zoom aberto."""
    from detector_zoom import janelas_do_zoom, listar_janelas_com_classe

    todas = listar_janelas_com_classe()
    assert todas, "EnumWindows não devolveu nenhuma janela"
    for janela in janelas_do_zoom():
        assert janela.classe.startswith(("ZP", "Zoom", "Conference")), (
            f"janela sem classe do Zoom classificada como Zoom: {janela!r}"
        )


# --- fonte ligada ao detector ------------------------------------------------


def _fonte(janelas, microfones):
    from deteccao_reuniao import FonteZoom

    return FonteZoom(lambda: janelas, lambda: microfones)


def test_fonte_zoom_e_sinal_forte_em_chamada():
    janelas = [_janela(titulo="Zoom Workplace", classe="ZPContentViewWndClass")]

    sinal = _fonte(janelas, []).ler()

    assert sinal.ativo is True
    assert sinal.forte is True
    assert sinal.fonte == "zoom"


def test_fonte_zoom_silenciosa_sem_chamada():
    sinal = _fonte([_janela(titulo="Zoom Workplace", classe="ZPFTEWndClass")], []).ler()

    assert sinal.ativo is False
    assert sinal.forte is False


def test_fonte_zoom_nao_derruba_o_monitor_quando_falha():
    """Fonte auxiliar quebrada nunca pode parar a detecção (FR-9.C)."""

    def _explode():
        raise OSError("EnumWindows indisponível")

    from deteccao_reuniao import FonteZoom

    sinal = FonteZoom(_explode, lambda: []).ler()

    assert sinal.ativo is False
    assert "indisponível" in sinal.detalhe


def test_detector_inicia_reuniao_so_com_a_fonte_zoom():
    """Zoom sem título reconhecível ainda inicia a gravação (FR-10.A3)."""
    from config import CONFIRMACAO_INICIO_MEET
    from deteccao_reuniao import DetectorReuniao

    janelas = [_janela(titulo="Zoom Workplace", classe="ZPContentViewWndClass")]
    detector = DetectorReuniao([_fonte(janelas, [])])

    mudancas = [detector.verificar() for _ in range(CONFIRMACAO_INICIO_MEET)]

    assert mudancas[-1] == "iniciou"
    assert detector.fontes_da_reuniao == ["zoom"]


def test_construir_detector_inclui_a_fonte_zoom():
    from monitor_reuniao import construir_detector

    nomes = [f.nome for f in construir_detector(None).fontes]

    assert "zoom" in nomes


# --- diagnóstico: como validar as classes na máquina do usuário --------------


def test_diagnostico_mostra_classe_da_janela_do_zoom():
    from diagnostico import checar_zoom

    itens = checar_zoom(
        [_janela(titulo="Zoom Workplace", classe="ZPContentViewWndClass")]
    )

    detalhes = " ".join(i["detalhe"] for i in itens)
    assert "ZPContentViewWndClass" in detalhes
    assert "chamada" in detalhes


def test_diagnostico_avisa_quando_nenhuma_classe_de_chamada_bate():
    """É assim que uma versão nova do Zoom se denuncia."""
    from diagnostico import checar_zoom

    itens = checar_zoom([_janela(titulo="Zoom Workplace", classe="ZPNovaClasse")])

    assert any("mudou de nome" in i["detalhe"] for i in itens)


def test_diagnostico_sem_zoom_aberto():
    from diagnostico import checar_zoom

    itens = checar_zoom([])

    assert len(itens) == 1
    assert "nenhuma janela" in itens[0]["detalhe"]
