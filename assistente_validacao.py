# -*- coding: utf-8 -*-
"""Contrato tipado do chat local (T-13.E3; histórico isolado chega em F1)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse


class PayloadInvalido(ValueError):
    """Payload fora do contrato → 400, nunca 500 nem eco."""


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ChatRequest:
    meeting_id: str
    transcript_revision: str
    generation_id: str
    question: str
    history: tuple
    model: str


def _texto(valor: object, campo: str, *, minimo: int, maximo: int) -> str:
    if not isinstance(valor, str):
        raise PayloadInvalido(f"campo {campo} inválido")
    texto = valor.strip() if campo in ("modelo", "transcricao") else valor
    if not (minimo <= len(texto) <= maximo):
        raise PayloadInvalido(f"campo {campo} inválido")
    return texto


def validar_chat_payload(value: object) -> dict:
    """Valida o corpo de /api/chat; nunca levanta além de PayloadInvalido."""
    import config as _config

    if not isinstance(value, dict):
        raise PayloadInvalido("corpo deve ser objeto")
    try:
        historico_bruto = value.get("historico", [])
    except AttributeError as exc:
        raise PayloadInvalido("corpo deve ser objeto") from exc
    if not isinstance(historico_bruto, list):
        raise PayloadInvalido("histórico inválido")
    if len(historico_bruto) > _config.MAX_HISTORICO_CHAT:
        raise PayloadInvalido("histórico excede o limite permitido")
    historico: list[ChatMessage] = []
    for item in historico_bruto:
        if not isinstance(item, dict):
            raise PayloadInvalido("item de histórico inválido")
        if item.get("role") not in ("user", "assistant"):
            raise PayloadInvalido("item de histórico inválido")
        conteudo = item.get("content")
        if not isinstance(conteudo, str) or not (1 <= len(conteudo) <= _config.CHAT_CONTEUDO_MAX_CHARS):
            raise PayloadInvalido("item de histórico inválido")
        historico.append(ChatMessage(role=item["role"], content=conteudo))
    modelo = _texto(value.get("modelo"), "modelo", minimo=1, maximo=_config.CHAT_MODELO_MAX_CHARS)
    transcricao = _texto(value.get("transcricao"), "transcricao", minimo=1, maximo=_config.CHAT_TRANSCRICAO_MAX_CHARS)
    if "/" in transcricao or "\\" in transcricao or ".." in transcricao:
        raise PayloadInvalido("campo transcricao inválido")
    return {
        "modelo": modelo,
        "transcricao": transcricao,
        "pergunta": _texto(value.get("pergunta"), "pergunta", minimo=1, maximo=_config.CHAT_PERGUNTA_MAX_CHARS),
        "historico": historico,
    }


def hosts_locais_aceitos(host: str | None) -> bool:
    """Host loopback com qualquer porta; resto e ausência reprovam (anti-rebinding)."""
    if not host or not isinstance(host, str):
        return False
    try:
        partes = urlparse(f"http://{host}")
    except Exception:  # noqa: BLE001
        return False
    return partes.hostname in ("127.0.0.1", "localhost")


def origem_permitida_chat(origin: str | None) -> bool:
    """Ausência (navegação direta/curl local) ou mesma origem; externa reprova."""
    if origin is None or origin == "":
        return True
    try:
        partes = urlparse(str(origin))
    except Exception:  # noqa: BLE001
        return False
    if partes.scheme != "http":
        return False
    return partes.hostname in ("127.0.0.1", "localhost")


def _id_reuniao(valor: object, campo: str) -> str:
    texto = _texto(valor, campo, minimo=1, maximo=120)
    if "/" in texto or "\\" in texto or ".." in texto:
        raise PayloadInvalido(f"campo {campo} inválido")
    return texto


def validar_chat_request(value: object) -> ChatRequest:
    """Contrato F1: conversa pertence a meeting_id + revisão; geração rastreável.

    Compatível com o payload legado (sem meeting_id → usa a transcrição).
    Janela: além de MAX_HISTORICO, corta as mais antigas (nunca rejeita a
    12ª pergunta por histórico longo).
    """
    import uuid as _uuid

    import config as _config

    if not isinstance(value, dict):
        raise PayloadInvalido("corpo deve ser objeto")
    valor_janela = dict(value)
    historico_bruto = valor_janela.get("historico", [])
    if isinstance(historico_bruto, list) and len(historico_bruto) > _config.MAX_HISTORICO_CHAT:
        valor_janela["historico"] = historico_bruto[-_config.MAX_HISTORICO_CHAT :]
    base = validar_chat_payload(valor_janela)
    assert isinstance(value, dict)
    meeting = value.get("meeting_id", None)
    if meeting is None:
        meeting = base["transcricao"]
    revisao = value.get("transcript_revision", "")
    if not isinstance(revisao, str) or len(revisao) > 120:
        raise PayloadInvalido("campo transcript_revision inválido")
    geracao = value.get("generation_id", None)
    if geracao is None:
        geracao = _uuid.uuid4().hex
    if not isinstance(geracao, str) or not (1 <= len(geracao) <= 80):
        raise PayloadInvalido("campo generation_id inválido")
    historico = list(base["historico"])
    return ChatRequest(
        meeting_id=_id_reuniao(meeting, "meeting_id"),
        transcript_revision=revisao,
        generation_id=geracao,
        question=base["pergunta"],
        history=tuple(historico),
        model=base["modelo"],
    )
