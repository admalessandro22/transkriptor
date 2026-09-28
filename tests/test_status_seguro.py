# -*- coding: utf-8 -*-
"""Testes de sanitização de logs (SEC-6)."""
from status_seguro import mensagem_e_sistema, sanitizar_para_log, sanitizar_toast_para_log


def test_mensagem_sistema_carregando_nao_sanitiza():
    msg = "Carregando modelo base..."
    assert mensagem_e_sistema(msg) is True
    assert sanitizar_para_log(msg) == "[modelo_carregando]"


def test_mensagem_sistema_diarizacao_nao_sanitiza():
    msg = "Diarização concluída: reuniao_diarizado.txt"
    assert sanitizar_para_log(msg) == "[diarizacao_status]"


def test_bloco_transcrito_e_sanitizado_no_log():
    msg = "Precisamos revisar o orçamento do trimestre na próxima reunião"
    assert mensagem_e_sistema(msg) is False
    assert sanitizar_para_log(msg) == "[conteúdo de transcrição omitido do log]"


MENSAGENS_DO_CICLO_DE_REUNIAO = [
    # Mensagens operacionais sem título nem texto livre continuam visíveis.
    "Reunião encerrada. Finalizando transcricao...",
    "Reunião encerrada e colocada na fila de transcrição.",
    "Esta reunião não será gravada.",
    "Gravação da reunião em andamento.",
    "Gravação automática pausada.",
    "Gravação automática retomada.",
    "Gravação descartada.",
]


def test_mensagens_do_ciclo_de_reuniao_aparecem_no_log():
    """SEC-6 continua fail-closed, mas mensagem de sistema não é fala."""
    for msg in MENSAGENS_DO_CICLO_DE_REUNIAO:
        assert mensagem_e_sistema(msg) is True, f"{msg!r} seria censurada"
        assert sanitizar_para_log(msg) == msg


def test_deteccao_registra_evento_sem_titulo():
    assert sanitizar_para_log("Reunião detectada. Iniciando gravação...") == "[meeting_detected]"


def test_fala_que_comeca_com_palavra_de_sistema_continua_censurada():
    """O allowlist é por prefixo de frase, não por palavra solta."""
    fala = "A gravação do contrato ficou com o jurídico, valor de R$ 2 milhões"
    assert sanitizar_para_log(fala) == "[conteúdo de transcrição omitido do log]"


def test_toast_nao_loga_conteudo_sensivel():
    titulo = "Transkriptor"
    mensagem = "Texto confidencial da reunião com dados sensíveis"
    assert sanitizar_toast_para_log(titulo, mensagem) == "[TOAST] Transkriptor: [mensagem omitida]"


def test_titulo_canario_nao_aparece_no_log():
    msg = "Reunião detectada (janela) — TITULO-CANARIO. Iniciando gravação..."
    assert "TITULO-CANARIO" not in sanitizar_para_log(msg)
