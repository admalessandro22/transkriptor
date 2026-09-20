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
