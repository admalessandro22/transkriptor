# -*- coding: utf-8 -*-
"""Identidade temporal de uma reunião (T-13.D1)."""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Mapping


class EnvelopeRejeitado(ValueError):
    """Envelope fora da sessão/intervalo/sequência — recusado, nunca adivinhado."""


TIPOS_ENVELOPE = frozenset(
    {
        "heartbeat",
        "participant_join",
        "participant_leave",
        "caption",
        "speaker_activity",
        "capabilities",
    }
)
TAMANHO_MAX_ENVELOPE = 4 * 1024
INCERTEZA_MAX_MS = 1500.0


@dataclass(frozen=True)
class SessaoReuniao:
    session_id: str
    meeting_key: str
    consented_at_utc: str
    first_frame_monotonic_ns: int | None
    policy_id: str
    rtt_ms: float = 0.0
    offset_ms: float = 0.0
    relogio_incerto: bool = True


def _consentimento_epoch_ms(consented_at_utc: str) -> int:
    texto = str(consented_at_utc).strip()
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    return int(datetime.datetime.fromisoformat(texto).timestamp() * 1000)


def criar_sessao(
    meeting_key: str, consented_at_utc: str, policy_id: str
) -> SessaoReuniao:
    if not str(meeting_key):
        raise ValueError("meeting_key vazio")
    _consentimento_epoch_ms(consented_at_utc)
    return SessaoReuniao(
        session_id=str(uuid.uuid4()),
        meeting_key=str(meeting_key),
        consented_at_utc=str(consented_at_utc),
        first_frame_monotonic_ns=None,
        policy_id=str(policy_id),
    )


def validar_envelope(evento: Mapping, sessao: SessaoReuniao) -> dict:
    """Valida envelope `schema_version=1` contra a sessão; recusa sem adivinhar."""
    if not isinstance(evento, Mapping):
        raise EnvelopeRejeitado("envelope não é objeto")
    try:
        serializado = json.dumps(dict(evento), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise EnvelopeRejeitado(f"envelope não serializável: {exc}") from exc
    if len(serializado.encode("utf-8")) > TAMANHO_MAX_ENVELOPE:
        raise EnvelopeRejeitado("envelope excede 4 KiB")
    for campo in (
        "event_id",
        "session_id",
        "connection_id",
        "tab_id",
        "meeting_key",
    ):
        valor = evento.get(campo)
        if not isinstance(valor, str) or not valor:
            raise EnvelopeRejeitado(f"campo obrigatório inválido: {campo}")
    seq = evento.get("seq")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        raise EnvelopeRejeitado("seq inválida")
    if evento.get("kind") not in TIPOS_ENVELOPE:
        raise EnvelopeRejeitado("kind desconhecido")
    for campo in ("client_wall_ms", "client_monotonic_ms", "received_monotonic_ns"):
        valor = evento.get(campo)
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            raise EnvelopeRejeitado(f"relógio inválido: {campo}")
    if evento["session_id"] != sessao.session_id:
        raise EnvelopeRejeitado("evento de outra sessão")
    if evento["meeting_key"] != sessao.meeting_key:
        raise EnvelopeRejeitado("evento de outra conferência")
    if int(evento["client_wall_ms"]) < _consentimento_epoch_ms(sessao.consented_at_utc):
        raise EnvelopeRejeitado("evento anterior ao consentimento")
    return dict(evento)


def registrar_primeiro_frame(sessao: SessaoReuniao, monotonic_ns: int) -> SessaoReuniao:
    """O instante zero é o primeiro frame confirmado; não se move depois."""
    if sessao.first_frame_monotonic_ns is not None:
        return sessao
    return dataclasses.replace(
        sessao, first_frame_monotonic_ns=int(monotonic_ns)
    )


def anotar_handshake(
    sessao: SessaoReuniao, *, rtt_ms: float, offset_ms: float
) -> SessaoReuniao:
    """Estima offset/ida-volta; incerteza >1,5 s marca relógio incerto."""
    rtt = max(0.0, float(rtt_ms))
    return dataclasses.replace(
        sessao,
        rtt_ms=rtt,
        offset_ms=float(offset_ms),
        relogio_incerto=(rtt / 2.0) > INCERTEZA_MAX_MS,
    )


def chave_reuniao(titulo: str | None, fontes) -> str:
    """Chave opaca e estável por conferência/instância (nunca o nome)."""
    base = f"{titulo or ''}\x00{','.join(sorted(str(f) for f in fontes or []))}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


def tempo_audio_ms(frames: int, sample_rate: int) -> int:
    """Duração de áudio por frames/taxa — relógio de parede nunca entra aqui."""
    if sample_rate <= 0 or frames <= 0:
        return 0
    return (int(frames) * 1000) // int(sample_rate)


class SessoesAtivas:
    """Um estado por conexão/aba/conferência; abas não se encerram entre si."""

    def __init__(self) -> None:
        self._por_conexao: dict[str, dict] = {}

    def obter_ou_criar(
        self,
        connection_id: str,
        tab_id: str,
        meeting_key: str,
        consented_at_utc: str,
        policy_id: str,
    ) -> SessaoReuniao:
        existente = self._por_conexao.get(connection_id)
        if existente is not None:
            return existente["sessao"]
        sessao = criar_sessao(meeting_key, consented_at_utc, policy_id)
        self._por_conexao[connection_id] = {
            "sessao": sessao,
            "tab_id": tab_id,
            "last_seq": -1,
            "event_ids": set(),
        }
        return sessao

    def encerrar_por_conexao(self, connection_id: str) -> None:
        self._por_conexao.pop(connection_id, None)

    def ativa(self, connection_id: str) -> bool:
        return connection_id in self._por_conexao

    def sessao_de(self, connection_id: str) -> SessaoReuniao:
        return self._por_conexao[connection_id]["sessao"]

    def aceitar_evento(self, connection_id: str, evento: Mapping) -> dict:
        registro = self._por_conexao.get(connection_id)
        if registro is None:
            raise EnvelopeRejeitado("conexão sem sessão")
        valido = validar_envelope(evento, registro["sessao"])
        if valido["connection_id"] != connection_id:
            raise EnvelopeRejeitado("evento de outra conexão")
        if valido["event_id"] in registro["event_ids"]:
            raise EnvelopeRejeitado("event_id duplicado")
        if int(valido["seq"]) <= int(registro["last_seq"]):
            raise EnvelopeRejeitado("seq antiga ou repetida")
        registro["event_ids"].add(valido["event_id"])
        registro["last_seq"] = int(valido["seq"])
        return valido
