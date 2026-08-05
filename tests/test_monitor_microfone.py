# -*- coding: utf-8 -*-
"""Microfone em uso como fonte de detecção (v1.4 — FR-9.3)."""
import pytest

from monitor_microfone import (
    apps_em_chamada,
    eh_app_conferencia,
    microfone_em_uso_por_conferencia,
    nome_executavel,
)

CHROME = r"C:#Program Files#Google#Chrome#Application#chrome.exe"
EDGE = r"C:#Program Files (x86)#Microsoft#Edge#Application#msedge.exe"
ZOOM = r"C:#Users#alguem#AppData#Roaming#Zoom#bin#Zoom.exe"
WISPR = r"C:#Users#alguem#AppData#Local#WisprFlow#app-1.6.399#Wispr Flow.exe"
EMPACOTADO = "Claude_pzs8sxrjxfjjc"


def test_nome_executavel_desfaz_a_codificacao_do_windows():
    assert nome_executavel(CHROME) == "chrome.exe"
    assert nome_executavel(ZOOM) == "zoom.exe"
    assert nome_executavel(EMPACOTADO) == "claude_pzs8sxrjxfjjc"


@pytest.mark.parametrize("chave,esperado", [(CHROME, True), (EDGE, True), (ZOOM, True),
                                            (WISPR, False), (EMPACOTADO, False)])
def test_apenas_apps_de_conferencia_contam(chave, esperado):
    assert eh_app_conferencia(chave) is esperado


def test_stop_zero_significa_microfone_em_uso():
    assert apps_em_chamada([(CHROME, 0)]) == ["chrome.exe"]


def test_stop_preenchido_significa_microfone_liberado():
    assert apps_em_chamada([(CHROME, 134303538875744501)]) == []


def test_ditado_por_voz_nao_vira_reuniao():
    """Regressão: WisprFlow usa o microfone o dia todo e não é reunião."""
    assert apps_em_chamada([(WISPR, 0), (EMPACOTADO, 0)]) == []


def test_varios_apps_sem_repeticao():
    entradas = [(CHROME, 0), (ZOOM, 0), (EDGE, 12345), (WISPR, 0)]
    assert sorted(apps_em_chamada(entradas)) == ["chrome.exe", "zoom.exe"]


def test_consulta_real_nunca_levanta():
    """Em qualquer máquina, a consulta devolve lista (pode ser vazia)."""
    assert isinstance(microfone_em_uso_por_conferencia(), list)


def test_falha_de_registro_devolve_lista_vazia(monkeypatch):
    def explode():
        raise OSError("registro indisponível")

    monkeypatch.setattr("monitor_microfone._ler_entradas_registro", explode)
    assert microfone_em_uso_por_conferencia() == []
