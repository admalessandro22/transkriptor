# -*- coding: utf-8 -*-
"""Helpers testáveis para ações do menu da bandeja."""


def confirmacao_saida_necessaria(gravando: bool) -> bool:
    return gravando


def saida_permitida(gravando: bool, usuario_confirmou: bool) -> bool:
    if not gravando:
        return True
    return usuario_confirmou


def texto_transcricao_manual(rodando: bool, combo: str | None = None) -> str:
    base = "Parar transcrição manual" if rodando else "Iniciar transcrição manual"
    if combo:
        return f"{base} ({combo})"
    return base


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