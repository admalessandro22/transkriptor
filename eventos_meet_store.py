# -*- coding: utf-8 -*-
"""Spool cifrado durável de eventos Meet por sessão (T-13.D4)."""
from __future__ import annotations

import datetime
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Iterator, Mapping

from artefatos import ArtifactRef, criar_referencia
from config import (
    MEET_EVENTOS_BUFFER,
    MEET_EVENTOS_DRENO_SEG,
    MEET_EVENTOS_SEGMENTO_BYTES,
    MEET_EVENTOS_SPOOL_MAX_BYTES,
)
from sessao_reuniao import EnvelopeRejeitado, SessaoReuniao, validar_envelope

logger = logging.getLogger(__name__)

FORMATO_SEGMENTO = "meet-events-jsonl-enc"
VERSAO_ARTEFATO = 1
TIPOS_CONTEUDO = frozenset(
    {"participant_join", "participant_leave", "caption", "speaker_activity", "capabilities"}
)


class ColetaBloqueada(RuntimeError):
    """Coleta de conteúdo bloqueada (sem chave ou coleta revogada)."""


def _chave_ok() -> bool:
    try:
        from crypto_storage import chave_disponivel, criptografia_ativa
    except Exception:  # noqa: BLE001
        return False
    try:
        return bool(criptografia_ativa()) and bool(chave_disponivel())
    except Exception:  # noqa: BLE001
        logger.debug("Cifra indisponível para eventos Meet", exc_info=True)
        return False


def _escrever_atomico(caminho: Path, dados: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(
        prefix=f"{caminho.stem}_", suffix=".tmp", dir=str(caminho.parent)
    )
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
        temporario = None
    finally:
        if temporario and os.path.isfile(temporario):
            try:
                os.remove(temporario)
            except OSError:
                pass


class EventStore:
    """Spool cifrado por sessão com ACK só após selo durável.

    Buffer em RAM (≤500 eventos); segmentos JSONL ≤1 MiB ou ≤1 s, cifrados
    individualmente via `crypto_storage`; índice só com metadados (seq, hash,
    tamanho, path — nunca nome/texto). Queda antes do selo perde o aberto;
    segmento rasgado invalida só a cauda a partir dele.
    """

    def __init__(
        self, root: Path, session: SessaoReuniao, cipher=None, ancora_refs=None
    ) -> None:
        del cipher  # adaptador usa crypto_storage (sem duplicar AES-GCM)
        self._raiz = Path(root) / session.session_id
        self._raiz.mkdir(parents=True, exist_ok=True)
        # Âncora das refs seladas (padrão: dir da sessão; app/worker usam a
        # raiz de transcrições para refs resolvíveis pelo job v2).
        self._ancora = Path(ancora_refs) if ancora_refs is not None else self._raiz
        self.sessao = session
        self._aberto: list[bytes] = []
        self._aberto_bytes = 0
        self._aberto_desde: float | None = None
        self._ack = -1
        self._proximo_indice = 0
        self._descartes = 0
        self._parcial = False
        self._revogada = False
        self._ultimo_segmento_selado: Path | None = None
        self._recuperar()

    @property
    def descartes(self) -> int:
        return self._descartes

    @property
    def parcial(self) -> bool:
        return self._parcial

    def estado(self) -> dict:
        return {
            "ack_seq": self._ack,
            "descartes": self._descartes,
            "parcial": self._parcial,
            "segmentos": self._proximo_indice,
        }

    # -- recuperação -----------------------------------------------------
    def _segmentos_selados(self) -> list[Path]:
        return sorted(self._raiz.glob("seg-*.jsonl.enc"))

    def _recuperar(self) -> None:
        for caminho in self._segmentos_selados():
            try:
                numero = int(caminho.stem.split("-")[1])
            except (IndexError, ValueError):
                numero = -1
            self._proximo_indice = max(self._proximo_indice, numero + 1)
        eventos = self._ler_selados_recuperando()
        if eventos:
            self._ack = max(e["seq"] for e in eventos)

    def _ler_selados_recuperando(self) -> list[dict]:
        from crypto_storage import ler_bytes_arquivo

        integros: list[dict] = []
        for caminho in self._segmentos_selados():
            try:
                plano = ler_bytes_arquivo(str(caminho))
            except Exception:  # noqa: BLE001 — escrita rasgada: para na cauda
                self._descartes += 1
                break
            try:
                linhas = plano.decode("utf-8").splitlines()
            except UnicodeDecodeError:
                self._descartes += 1
                break
            ok = True
            for linha in linhas:
                try:
                    evento = json.loads(linha)
                except ValueError:
                    ok = False
                    break
                if not isinstance(evento, dict) or "seq" not in evento:
                    ok = False
                    break
                integros.append(evento)
            if not ok:
                self._descartes += 1
                break
        return integros

    # -- escrita ---------------------------------------------------------
    def _exige_conteudo(self, kind: str) -> None:
        if self._revogada:
            raise ColetaBloqueada("coleta de conteúdo revogada para esta sessão")
        if kind in TIPOS_CONTEUDO and not _chave_ok():
            raise ColetaBloqueada("cifra indisponível para legendas/nomes")

    def append(self, event: Mapping) -> int:
        try:
            valido = validar_envelope(event, self.sessao)
        except EnvelopeRejeitado:
            raise
        kind = str(valido.get("kind", ""))
        if kind == "heartbeat":
            return self._ack
        self._exige_conteudo(kind)
        linha = json.dumps(valido, ensure_ascii=False).encode("utf-8") + b"\n"
        if self._aberto_desde is None:
            self._aberto_desde = time.monotonic()
        self._aberto.append(linha)
        self._aberto_bytes += len(linha)
        if (
            len(self._aberto) >= MEET_EVENTOS_BUFFER
            or self._aberto_bytes >= MEET_EVENTOS_SEGMENTO_BYTES
            or (time.monotonic() - (self._aberto_desde or 0.0)) >= MEET_EVENTOS_DRENO_SEG
        ):
            self.descarregar()
        return self._ack

    def _tamanho_spool(self) -> int:
        return sum(
            caminho.stat().st_size
            for caminho in self._segmentos_selados()
            if caminho.is_file()
        )

    def descarregar(self, forcar: bool = False) -> int:
        if not self._aberto:
            return self._ack
        if not forcar and (
            self._aberto_bytes < MEET_EVENTOS_SEGMENTO_BYTES
            and len(self._aberto) < MEET_EVENTOS_BUFFER
            and (time.monotonic() - (self._aberto_desde or 0.0)) < MEET_EVENTOS_DRENO_SEG
        ):
            return self._ack
        from crypto_storage import ler_bytes_arquivo, salvar_bytes_arquivo

        if self._tamanho_spool() + self._aberto_bytes > MEET_EVENTOS_SPOOL_MAX_BYTES:
            self._descartes += len(self._aberto)
            self._parcial = True
            self._aberto = []
            self._aberto_bytes = 0
            self._aberto_desde = None
            return self._ack
        plano = b"".join(self._aberto)
        destino = self._raiz / f"seg-{self._proximo_indice:06d}.jsonl.enc"
        salvar_bytes_arquivo(str(destino), plano)
        try:
            if ler_bytes_arquivo(str(destino)) != plano:
                raise ValueError("validação de leitura do segmento")
        except Exception as exc:  # noqa: BLE001
            try:
                destino.unlink()
            except OSError:
                pass
            raise ValueError(f"selo sem durabilidade: {exc}") from exc
        self._ultimo_segmento_selado = destino
        self._proximo_indice += 1
        try:
            ultimo = json.loads(self._aberto[-1].decode("utf-8"))
            self._ack = int(ultimo.get("seq", self._ack))
        except (ValueError, TypeError):
            pass
        self._aberto = []
        self._aberto_bytes = 0
        self._aberto_desde = None
        self._gravar_indice()
        return self._ack

    def _gravar_indice(self) -> None:
        from artefatos import sha256_arquivo

        entradas = []
        for caminho in self._segmentos_selados():
            entradas.append(
                {
                    "path": caminho.name,
                    "sha256": sha256_arquivo(caminho),
                    "size_bytes": caminho.stat().st_size,
                }
            )
        _escrever_atomico(
            self._raiz / "indice.json",
            json.dumps(
                {"segments": entradas, "descartes": self._descartes}, ensure_ascii=False
            ).encode("utf-8"),
        )

    def read_events(self) -> Iterator[dict]:
        yield from self._ler_selados_recuperando()
        for linha in self._aberto:
            try:
                evento = json.loads(linha.decode("utf-8"))
            except ValueError:
                continue
            if isinstance(evento, dict):
                yield evento

    def seal(self) -> tuple[ArtifactRef, ...]:
        self.descarregar(forcar=True)
        refs = []
        for caminho in self._segmentos_selados():
            refs.append(
                criar_referencia(
                    caminho,
                    self._ancora,
                    format=FORMATO_SEGMENTO,
                    schema_version=VERSAO_ARTEFATO,
                )
            )
        return tuple(refs)

    def revogar(self) -> None:
        self._revogada = True


def eventos_elegiveis_exclusao(
    root_sessoes, manifesto, agora: datetime.datetime, *, dias: int = 7
) -> list[str]:
    """Brutos elegíveis só 7 dias após ResultManifest válido (DU-10)."""
    from resultado_reuniao import carregar_manifesto, validar_manifesto

    try:
        manifesto_path = Path(manifesto)
        if not validar_manifesto(manifesto_path, manifesto_path.parent):
            return []
        criado = carregar_manifesto(manifesto_path).created_at
        texto = str(criado).strip()
        if texto.endswith("Z"):
            texto = texto[:-1] + "+00:00"
        instante = datetime.datetime.fromisoformat(texto)
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=datetime.timezone.utc)
        if (agora - instante).total_seconds() < dias * 86400:
            return []
    except Exception:  # noqa: BLE001 — manifesto ilegível nunca libera exclusão
        return []
    raiz = Path(root_sessoes)
    if not raiz.is_dir():
        return []
    return sorted(p.name for p in raiz.iterdir() if p.is_dir())
