# -*- coding: utf-8 -*-
"""Ponte WebSocket local para eventos da extensão Meet (FR-8.2)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import secrets
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from config import (
    MAX_FILA_MEET_WS,
    MAX_MENSAGEM_MEET_WS,
    MAX_NOME_PARTICIPANTE,
    MAX_TEXTO_LEGENDA,
)

logger = logging.getLogger(__name__)

ORIGENS_PERMITIDAS_PREFIXOS = (
    "chrome-extension://",
    "http://127.0.0.1",
    "http://localhost",
)


def sanitizar_nome_participante(nome: str) -> str:
    """Remove caracteres de controle e limita tamanho (SEC-6 / diarizado seguro)."""
    limpo = "".join(c for c in str(nome) if c.isprintable() or c.isspace())
    limpo = " ".join(limpo.split())
    return limpo[:MAX_NOME_PARTICIPANTE]


def sanitizar_texto_legenda(texto: str) -> str:
    """Sanitiza texto de legenda como o nome e trunca em MAX_TEXTO_LEGENDA (FR-5.4)."""
    limpo = "".join(c for c in str(texto) if c.isprintable() or c.isspace())
    limpo = " ".join(limpo.split())
    return limpo[:MAX_TEXTO_LEGENDA]


def eh_evento_estado(dados: Any) -> bool:
    """True para o heartbeat de estado da reunião enviado pela extensão (FR-9.3)."""
    return isinstance(dados, dict) and str(dados.get("tipo", "")) == "reuniao"


def estado_reuniao_do_evento(dados: Any) -> bool:
    """Lê `{tipo:"reuniao", ativa: bool}` — qualquer valor falso encerra."""
    return bool(isinstance(dados, dict) and dados.get("ativa"))


def normalizar_evento(dados: Any) -> dict | None:
    """Normaliza payload `{nome, ts_ms, tipo, texto?}` para a fila interna (FR-5.4)."""
    if not isinstance(dados, dict):
        return None
    nome = sanitizar_nome_participante(dados.get("nome", ""))
    if not nome:
        return None
    try:
        ts_ms = int(dados.get("ts_ms", 0))
    except (TypeError, ValueError):
        ts_ms = 0
    tipo = str(dados.get("tipo", "ativo"))
    evento = {
        "nome": nome,
        "ts_ms": ts_ms,
        "ts_sec": ts_ms / 1000.0,
        "tipo": tipo,
    }
    if "texto" in dados and dados.get("texto") is not None:
        texto = sanitizar_texto_legenda(dados.get("texto", ""))
        if texto:
            evento["texto"] = texto
    return evento


def origem_permitida(origin: str | None) -> bool:
    if not origin:
        return True
    return any(origin.startswith(prefixo) for prefixo in ORIGENS_PERMITIDAS_PREFIXOS)


def token_url_valido(recebido: str | None, esperado: str) -> bool:
    return bool(recebido) and recebido == esperado


def _token_da_url(path: str) -> str | None:
    query = parse_qs(urlparse(path).query)
    valores = query.get("token", [])
    return valores[0] if valores else None


class MeetBridge:
    """Fila thread-safe de eventos recebidos da extensão Chrome."""

    def __init__(self, token: str | None = None, max_fila: int = MAX_FILA_MEET_WS) -> None:
        self.token = token or secrets.token_urlsafe(24)
        self.fila: queue.Queue = queue.Queue(maxsize=max_fila)
        self._parar = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_future: asyncio.Future | None = None
        self._estado_lock = threading.Lock()
        self._reuniao_ativa = False
        self._visto_em: float = 0.0

    def reuniao_ativa(self, agora: float | None = None, validade: float = 20.0) -> bool:
        """FR-9.3: a extensão reportou reunião ativa há menos de `validade` s.

        O heartbeat expira de propósito: se a aba do Meet for fechada de vez, a
        extensão morre sem avisar e o estado precisa cair sozinho.
        """
        import time as _time

        agora = _time.monotonic() if agora is None else agora
        with self._estado_lock:
            if not self._reuniao_ativa:
                return False
            return (agora - self._visto_em) <= validade

    def registrar_estado_reuniao(self, ativa: bool, agora: float | None = None) -> None:
        import time as _time

        agora = _time.monotonic() if agora is None else agora
        with self._estado_lock:
            self._reuniao_ativa = bool(ativa)
            self._visto_em = agora

    def registrar_evento(self, dados: Any) -> None:
        if eh_evento_estado(dados):
            self.registrar_estado_reuniao(estado_reuniao_do_evento(dados))
            return
        ev = normalizar_evento(dados)
        if ev is None:
            return
        try:
            self.fila.put_nowait(ev)
        except queue.Full:
            logger.debug("Fila Meet bridge cheia; evento descartado.")

    def processar_mensagem(self, mensagem: str | dict) -> None:
        if isinstance(mensagem, str):
            if len(mensagem.encode("utf-8")) > MAX_MENSAGEM_MEET_WS:
                return
            try:
                dados = json.loads(mensagem)
            except json.JSONDecodeError:
                return
            self.registrar_evento(dados)
        elif isinstance(mensagem, dict):
            self.registrar_evento(mensagem)

    def drenar_eventos(self) -> list[dict]:
        eventos: list[dict] = []
        while True:
            try:
                eventos.append(self.fila.get_nowait())
            except queue.Empty:
                break
        return eventos

    def parar(self) -> None:
        self._parar.set()
        if self._loop and self._stop_future and not self._stop_future.done():
            self._loop.call_soon_threadsafe(self._stop_future.set_result, None)


async def _servidor_ws(bridge: MeetBridge, host: str, porta: int) -> None:
    import websockets

    async def handler(websocket) -> None:
        origin = websocket.request.headers.get("Origin")
        if not origem_permitida(origin):
            await websocket.close(1008, "Origin not allowed")
            return
        token_url = _token_da_url(websocket.request.path or "")
        if not token_url_valido(token_url, bridge.token):
            await websocket.close(1008, "Unauthorized")
            return
        try:
            async for mensagem in websocket:
                bridge.processar_mensagem(mensagem)
        except Exception:
            logger.debug("Cliente WebSocket desconectado", exc_info=True)

    bridge._loop = asyncio.get_running_loop()
    bridge._stop_future = bridge._loop.create_future()
    async with websockets.serve(handler, host, porta):
        await bridge._stop_future


def iniciar_bridge_em_thread(
    bridge: MeetBridge,
    host: str = "127.0.0.1",
    porta: int = 5051,
) -> threading.Thread:
    """Inicia servidor WebSocket em thread daemon. Retorna a thread."""

    def _run() -> None:
        try:
            asyncio.run(_servidor_ws(bridge, host, porta))
        except Exception:
            logger.exception("Erro no servidor Meet bridge")

    thread = threading.Thread(target=_run, daemon=True, name="meet-bridge")
    thread.start()
    return thread


def sincronizar_token_extensao(token: str, base_dir: str) -> None:
    """Grava token para a extensão Chrome (config.js local)."""
    caminho = os.path.join(base_dir, "extension", "meet", "config.js")
    conteudo = (
        "// Gerado automaticamente pelo Transkriptor — não editar manualmente.\n"
        f'const MEET_WS_TOKEN = "{token}";\n'
    )
    try:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except OSError:
        logger.warning("Não foi possível sincronizar token da extensão Meet.", exc_info=True)