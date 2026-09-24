# -*- coding: utf-8 -*-
"""Metadados de transcrição para a Central: rótulo do usuário, badge VOCÊ e detalhes sob demanda."""
from __future__ import annotations

from config import ROTULO_USUARIO


def rotulo_usuario_efetivo() -> str:
    """Lê rotulo_usuario de config_user.json; fallback para ROTULO_USUARIO (FR-5.7)."""
    try:
        import config_user

        valor = config_user.carregar().get("rotulo_usuario")
        if valor:
            return str(valor)
    except Exception:
        pass
    return ROTULO_USUARIO


def transcricao_contem_voce(conteudo: str, rotulo: str | None = None) -> bool:
    """True se diarização inclui o rótulo efetivo do usuário (FR-5.7)."""
    rotulo_efetivo = rotulo if rotulo is not None else ROTULO_USUARIO
    return bool(rotulo_efetivo) and rotulo_efetivo in conteudo


def detalhes_transcricao(nome: str, tipo: str, rotulo: str, ler) -> dict:
    """Preview e `com_sua_voz` exigem abrir o texto; só sob demanda (UX-14.B2)."""
    conteudo, preview = "", ""
    try:
        conteudo = ler(nome) or ""
        linhas = [
            l.strip()
            for l in conteudo[:500].split("\n")
            if l.strip() and not l.startswith("===")
        ]
        preview = linhas[0][:80] if linhas else ""
    except Exception:
        pass
    return {
        "preview": preview,
        "com_sua_voz": tipo == "diarizado" and transcricao_contem_voce(conteudo, rotulo),
    }
