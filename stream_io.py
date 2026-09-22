# -*- coding: utf-8 -*-
"""Adaptador incremental de iterador de bytes para leitores binários."""
from __future__ import annotations

import io


class IteratorReader(io.RawIOBase):
    """Mantém somente o chunk corrente do iterador em memória."""

    def __init__(self, chunks):
        super().__init__()
        self._chunks = iter(chunks)
        self._atual = memoryview(b"")
        self._fim = False

    def readable(self):
        return True

    def readinto(self, destino):
        if self.closed:
            raise ValueError("leitor fechado")
        view = memoryview(destino)
        copiados = 0
        while copiados < len(view):
            if not self._atual:
                if self._fim:
                    break
                try:
                    self._atual = memoryview(next(self._chunks))
                except StopIteration:
                    self._fim = True
                    break
                if not self._atual:
                    continue
            quantidade = min(len(view) - copiados, len(self._atual))
            view[copiados:copiados + quantidade] = self._atual[:quantidade]
            self._atual = self._atual[quantidade:]
            copiados += quantidade
        return copiados

    def close(self):
        fechar = getattr(self._chunks, "close", None)
        if callable(fechar):
            fechar()
        super().close()
