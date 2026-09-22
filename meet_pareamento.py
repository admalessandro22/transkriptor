# -*- coding: utf-8 -*-
"""Pareamento local da extensão Meet com convite de uso único."""
from __future__ import annotations

import secrets
import threading
import time

from config import MEET_CONVITE_SEG, MEET_SESSAO_SEG


class ConviteInvalido(ValueError):
    """Convite de pareamento inexistente, expirado ou já utilizado."""


class Pareador:
    """Emite um convite e o troca por uma credencial revogável da sessão."""

    def __init__(
        self,
        validade_convite_seg: float = MEET_CONVITE_SEG,
        validade_sessao_seg: float = MEET_SESSAO_SEG,
    ) -> None:
        self.validade_convite_seg = float(validade_convite_seg)
        self.validade_sessao_seg = float(validade_sessao_seg)
        self._lock = threading.Lock()
        self._convites: dict[str, float] = {}
        self._sessoes: dict[str, float] = {}

    def gerar_convite(self, validade_seg: float | None = None) -> str:
        codigo = "pair-" + secrets.token_urlsafe(18)
        expira = time.monotonic() + float(
            self.validade_convite_seg if validade_seg is None else validade_seg
        )
        with self._lock:
            self._convites[codigo] = expira
        return codigo

    def trocar_convite(self, codigo: str) -> str:
        """Consome o convite e devolve a credencial da sessão (uso único)."""
        with self._lock:
            expira = self._convites.pop(str(codigo), None)
            if expira is None or time.monotonic() >= expira:
                raise ConviteInvalido("convite inexistente, expirado ou já usado")
            token = "sess-" + secrets.token_urlsafe(24)
            self._sessoes[token] = time.monotonic() + self.validade_sessao_seg
            return token

    def autenticar(self, credencial: str | None) -> tuple[str, bool]:
        """Valida sessão ou troca convite; devolve (token, era_convite)."""
        if not credencial:
            raise ConviteInvalido("credencial ausente")
        with self._lock:
            expira = self._sessoes.get(str(credencial))
            if expira is not None:
                if time.monotonic() <= expira:
                    return str(credencial), False
                del self._sessoes[str(credencial)]
        if str(credencial).startswith("pair-"):
            return self.trocar_convite(str(credencial)), True
        raise ConviteInvalido("token de sessão inválido ou revogado")

    def validar_token(self, token: str | None) -> bool:
        try:
            self.autenticar(token)
            return True
        except ConviteInvalido:
            return False

    def revogar_token(self, token: str) -> None:
        with self._lock:
            self._sessoes.pop(str(token), None)
