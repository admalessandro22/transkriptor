# -*- coding: utf-8 -*-
"""Sanitização de mensagens de status para logs (SEC-6)."""

PREFIXOS_MENSAGEM_SISTEMA = (
    "Carregando",
    "Modelo pronto",
    "Capturando",
    "Erro",
    "Iniciando",
    "Diarização",
    "Transcrição",
    "Transcricao",
    "Sem segmentos",
    "Watchdog",
    "Meet",
    "Salvo:",
    "Assistente",
    "Detec",
    "Ponte",
    "ERRO",
    "Separação",
    "Reiniciando",
    "Ja transcrevendo",
    "Finalizando",
    "encerrada",
    "ativa em",
    "rodando em",
    "pausada",
    "retomada",
    "desativada",
    "Abrindo",
    "Aguardando",
    "Cadastro",
    "perfil",
    "nomes Meet",
    "legendas",
    "Vozes separadas",
    "offline",
    "Parar",
    "Sair",
    "Encerrando",
)

MSG_LOG_TRANSCRICAO_OMITIDA = "[conteúdo de transcrição omitido do log]"


def mensagem_e_sistema(msg: str) -> bool:
    if not msg or not str(msg).strip():
        return True
    texto = str(msg).strip()
    for prefixo in PREFIXOS_MENSAGEM_SISTEMA:
        if texto.startswith(prefixo):
            return True
    if ".txt" in texto or "127.0.0.1" in texto:
        return True
    return False


def sanitizar_para_log(msg: str) -> str:
    if mensagem_e_sistema(msg):
        return msg
    return MSG_LOG_TRANSCRICAO_OMITIDA


def sanitizar_toast_para_log(titulo: str, _mensagem: str) -> str:
    return f"[TOAST] {titulo}: [mensagem omitida]"