# -*- coding: utf-8 -*-
"""Helpers testáveis para ações do menu da bandeja."""

IDYES = 6
IDNO = 7
MB_TIMEDOUT = 32000  # retorno de MessageBoxTimeoutW quando o tempo expira


def resposta_continuar_gravacao(retorno) -> bool:
    """FR-2.9: só recusa a gravação com 'Não' explícito; timeout ou erro continuam."""
    return retorno != IDNO


def deve_iniciar_gravacao_auto(recusa_reuniao_ativa: bool) -> bool:
    """FR-2.10: recusa vale até o fim da reunião atual."""
    return not recusa_reuniao_ativa


def confirmacao_saida_necessaria(gravando: bool) -> bool:
    return gravando


def saida_permitida(gravando: bool, usuario_confirmou: bool) -> bool:
    if not gravando:
        return True
    return usuario_confirmou


def texto_transcricao_manual(rodando: bool) -> str:
    return "Parar transcrição manual" if rodando else "Iniciar transcrição manual"


def texto_deteccao_menu(deteccao_ativa: bool) -> str:
    """UX-2.1: deixa claro que pausa = não grava reuniões."""
    if deteccao_ativa:
        return "Pausar gravação automática (NÃO grava reuniões)"
    return "Retomar gravação automática"


def deve_confirmar_pausa(deteccao_ativa: bool) -> bool:
    """Só pede confirmação ao pausar (não ao retomar)."""
    return deteccao_ativa


def deve_toast_meet_em_pausa(deteccao_ativa: bool, mudanca: str, ja_avisou: bool) -> bool:
    """Toast único por reunião quando Meet inicia durante pausa (FR-2.6)."""
    if deteccao_ativa:
        return False
    if mudanca != "iniciou":
        return False
    return not ja_avisou


def deve_parar_transcricao_por_meet(mudanca: str, modo_manual: bool) -> bool:
    """Transcrição manual não deve ser encerrada quando o detector vê Meet fechar."""
    if mudanca != "encerrou":
        return False
    return not modo_manual