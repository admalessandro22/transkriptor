# -*- coding: utf-8 -*-
"""Testes de sanitização de logs (SEC-6)."""
from status_seguro import mensagem_e_sistema, sanitizar_para_log, sanitizar_toast_para_log


def test_mensagem_sistema_carregando_nao_sanitiza():
    msg = "Carregando modelo base..."
    assert mensagem_e_sistema(msg) is True
    assert sanitizar_para_log(msg) == msg


def test_mensagem_sistema_diarizacao_nao_sanitiza():
    msg = "Diarização concluída: reuniao_diarizado.txt"
    assert sanitizar_para_log(msg) == msg


def test_bloco_transcrito_e_sanitizado_no_log():
    msg = "Precisamos revisar o orçamento do trimestre na próxima reunião"
    assert mensagem_e_sistema(msg) is False
    assert sanitizar_para_log(msg) == "[conteúdo de transcrição omitido do log]"


def test_toast_nao_loga_conteudo_sensivel():
    titulo = "Transkriptor"
    mensagem = "Texto confidencial da reunião com dados sensíveis"
    assert sanitizar_toast_para_log(titulo, mensagem) == "[TOAST] Transkriptor: [mensagem omitida]"