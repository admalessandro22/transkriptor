# -*- coding: utf-8 -*-
"""Helpers testáveis para ações do menu da bandeja."""


def confirmacao_saida_necessaria(gravando: bool) -> bool:
    return gravando


def saida_permitida(gravando: bool, usuario_confirmou: bool) -> bool:
    if not gravando:
        return True
    return usuario_confirmou


def texto_transcricao_manual(rodando: bool) -> str:
    return "Parar transcrição manual" if rodando else "Transcrição manual"


def deve_parar_transcricao_por_meet(mudanca: str, modo_manual: bool) -> bool:
    """Transcrição manual não deve ser encerrada quando o detector vê Meet fechar."""
    if mudanca != "encerrou":
        return False
    return not modo_manual