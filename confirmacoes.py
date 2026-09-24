# -*- coding: utf-8 -*-
"""Textos únicos de consequência para ações que exigem confirmação (UX-14.D2/E4).

A bandeja (MessageBoxW) e a Central (diálogo próprio) usam o mesmo texto; a
consequência diz o que muda e o que não muda, sem jargão.
"""
from __future__ import annotations

CONSEQUENCIAS: dict[str, dict[str, str]] = {
    "pausar_gravacao": {
        "titulo": "Pausar a gravação automática?",
        "consequencia": "Enquanto pausado, o Transkriptor NÃO grava nenhuma reunião. Reuniões que acontecerem nesse período não terão transcrição.",
        "confirmar": "Pausar",
    },
    "sair_gravando": {
        "titulo": "Parar a gravação e sair?",
        "consequencia": "A reunião em andamento é interrompida agora. O áudio já capturado é preservado e enfileirado para processamento.",
        "confirmar": "Parar e sair",
    },
    "modo_protegido": {
        "titulo": "Ativar o modo protegido para novas reuniões?",
        "consequencia": "Novas reuniões terão resultado e eventos cifrados em repouso; exportar texto legível passa a exigir ação explícita. Arquivos existentes não são migrados nem apagados.",
        "confirmar": "Ativar proteção",
    },
    "apagar_perfil_voz": {
        "titulo": "Apagar o seu perfil de voz?",
        "consequencia": "A identificação VOCÊ deixa de funcionar até um novo cadastro de 20 segundos. Não pode ser desfeito.",
        "confirmar": "Apagar perfil",
    },
    "exportar_legivel": {
        "titulo": "Exportar o texto legível desta reunião?",
        "consequencia": "O arquivo conterá o texto legível da reunião, com nomes e falas, fora da proteção do aplicativo. Guarde-o com cuidado.",
        "confirmar": "Exportar",
    },
}


def consequencia(acao: str) -> dict[str, str]:
    """Textos da ação; KeyError para ação desconhecida (falha explícita, nunca texto vazio)."""
    return dict(CONSEQUENCIAS[acao])


def texto_para_messagebox(acao: str) -> str:
    """Título e consequência numa string para o MessageBoxW da bandeja."""
    dados = consequencia(acao)
    return f"{dados['titulo']}\n\n{dados['consequencia']}"
