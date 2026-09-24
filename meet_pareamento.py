# -*- coding: utf-8 -*-
"""Pareamento local da extensão Meet com convite de uso único.

A credencial trocada pelo convite persiste entre reinícios do app quando o
`Pareador` recebe `arquivo` (decisão do usuário, 24/09/2026): o disco guarda
só o SHA-256 da credencial e a validade em relógio de parede; o uso renova a
validade. Sem `arquivo`, tudo fica em memória como antes.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

from config import MEET_CONVITE_SEG, MEET_SESSAO_SEG

logger = logging.getLogger(__name__)
RENOVAR_APOS_SEG = 24 * 3600  # regrava a validade no máximo uma vez por dia


class ConviteInvalido(ValueError):
    """Convite de pareamento inexistente, expirado ou já utilizado."""


class Pareador:
    """Emite um convite e o troca por uma credencial revogável da sessão."""

    MAX_SESSOES = 5

    def __init__(
        self,
        validade_convite_seg: float = MEET_CONVITE_SEG,
        validade_sessao_seg: float = MEET_SESSAO_SEG,
        arquivo: str | os.PathLike | None = None,
    ) -> None:
        self.validade_convite_seg = float(validade_convite_seg)
        self.validade_sessao_seg = float(validade_sessao_seg)
        self._lock = threading.Lock()
        self._convites: dict[str, float] = {}
        # hash da credencial -> expiração em time.time() (sobrevive a reinício)
        self._sessoes: dict[str, float] = {}
        self._arquivo = Path(arquivo) if arquivo is not None else None
        self._carregar()

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    def _carregar(self) -> None:
        if self._arquivo is None or not self._arquivo.is_file():
            return
        try:
            dados = json.loads(self._arquivo.read_text(encoding="utf-8"))
            agora = time.time()
            for h, expira in dict(dados.get("sessoes", {})).items():
                if isinstance(h, str) and len(h) == 64 and isinstance(expira, (int, float)) and expira > agora:
                    self._sessoes[h] = float(expira)
        except (OSError, ValueError, TypeError, AttributeError):
            logger.warning("Pareamento Meet salvo ilegível; será preciso parear de novo.")
            self._sessoes.clear()

    def _salvar(self) -> None:
        """Grava atomicamente; chamado sob `self._lock`, sem callbacks."""
        if self._arquivo is None:
            return
        try:
            self._arquivo.parent.mkdir(parents=True, exist_ok=True)
            conteudo = json.dumps({"versao": 1, "sessoes": self._sessoes}, indent=0)
            fd, temp = tempfile.mkstemp(dir=self._arquivo.parent, prefix=".meet_pareamento.")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(conteudo)
            os.replace(temp, self._arquivo)
        except OSError:
            logger.warning("Não foi possível salvar o pareamento Meet; ele vale só até o app fechar.")

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
            self._sessoes[self._hash(token)] = time.time() + self.validade_sessao_seg
            if len(self._sessoes) > self.MAX_SESSOES:
                for h, _ in sorted(self._sessoes.items(), key=lambda par: par[1])[: len(self._sessoes) - self.MAX_SESSOES]:
                    del self._sessoes[h]
            self._salvar()
            return token

    def autenticar(self, credencial: str | None) -> tuple[str, bool]:
        """Valida sessão ou troca convite; devolve (token, era_convite)."""
        if not credencial:
            raise ConviteInvalido("credencial ausente")
        with self._lock:
            h = self._hash(credencial)
            expira = self._sessoes.get(h)
            if expira is not None:
                agora = time.time()
                if agora <= expira:
                    nova = agora + self.validade_sessao_seg
                    if nova - expira >= RENOVAR_APOS_SEG:
                        self._sessoes[h] = nova
                        self._salvar()
                    return str(credencial), False
                del self._sessoes[h]
                self._salvar()
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
            if self._sessoes.pop(self._hash(token), None) is not None:
                self._salvar()
