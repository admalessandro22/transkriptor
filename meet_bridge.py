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
    MEET_CONVITE_SEG,
    MEET_SESSAO_SEG,
    MEET_WS_BURST,
    MEET_WS_EVENTOS_POR_SEG,
    MEET_WS_MAX_BYTES,
    MEET_WS_MAX_CONEXOES,
)

logger = logging.getLogger(__name__)

_ORIGEM_EXTENSAO_RE = None


def _origem_extensao_re():
    global _ORIGEM_EXTENSAO_RE
    if _ORIGEM_EXTENSAO_RE is None:
        import re as _re

        _ORIGEM_EXTENSAO_RE = _re.compile(r"^[a-p]{16,32}$")
    return _ORIGEM_EXTENSAO_RE


class ConviteInvalido(ValueError):
    """Convite de pareamento inexistente, expirado ou já utilizado."""


class Pareador:
    """Pareamento local de uso único (T-13.D2).

    O app gera um convite e o exibe ao usuário; a página de pareamento da
    extensão entrega o código ao service worker, que o troca pela credencial
    da sessão no primeiro handshake. Convite não é reutilizável; a credencial
    vale por sessão, aceita reconexões e pode ser revogada.
    """

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
        import time as _time

        codigo = "pair-" + secrets.token_urlsafe(18)
        expira = _time.monotonic() + float(
            self.validade_convite_seg if validade_seg is None else validade_seg
        )
        with self._lock:
            self._convites[codigo] = expira
        return codigo

    def trocar_convite(self, codigo: str) -> str:
        """Consome o convite e devolve a credencial da sessão (uso único)."""
        import time as _time

        with self._lock:
            expira = self._convites.pop(str(codigo), None)
            if expira is None or _time.monotonic() >= expira:
                raise ConviteInvalido("convite inexistente, expirado ou já usado")
            token = "sess-" + secrets.token_urlsafe(24)
            self._sessoes[token] = _time.monotonic() + self.validade_sessao_seg
            return token

    def autenticar(self, credencial: str | None) -> tuple[str, bool]:
        """Valida sessão ou troca convite; devolve (token, era_convite)."""
        import time as _time

        if not credencial:
            raise ConviteInvalido("credencial ausente")
        with self._lock:
            expira = self._sessoes.get(str(credencial))
            if expira is not None:
                if _time.monotonic() <= expira:
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
    """Origin exata de extensão autorizada ou loopback local (T-13.D2).

    Sem prefixo enganoso (`http://localhost.example.test` reprova) e sem
    ausência: `None` reprova no listener de produção.
    """
    if not origin or not isinstance(origin, str):
        return False
    try:
        partes = urlparse(origin)
    except Exception:  # noqa: BLE001
        return False
    if partes.scheme == "chrome-extension":
        return bool(_origem_extensao_re().fullmatch(partes.hostname or ""))
    if partes.scheme == "http" and partes.hostname in ("127.0.0.1", "localhost"):
        return True
    return False


def token_url_valido(recebido: str | None, esperado: str) -> bool:
    return bool(recebido) and recebido == esperado


def _token_da_url(path: str) -> str | None:
    query = parse_qs(urlparse(path).query)
    valores = query.get("token", [])
    return valores[0] if valores else None


class MeetBridge:
    """Fila thread-safe de eventos recebidos da extensão Chrome."""

    def __init__(
        self,
        token: str | None = None,
        max_fila: int = MAX_FILA_MEET_WS,
        pareador: Pareador | None = None,
    ) -> None:
        self.token = token or secrets.token_urlsafe(24)
        self.pareador = pareador
        self.fila: queue.Queue = queue.Queue(maxsize=max_fila)
        self._parar = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_future: asyncio.Future | None = None
        self._estado_lock = threading.Lock()
        self._reuniao_ativa = False
        self._visto_em: float = 0.0
        self._titulo_meet: str | None = None
        self._sessao_por_conexao: dict[str, str] = {}
        self._conexoes_autenticadas = 0
        self.contador_descarte_rajada = 0
        self._store = None

    def definir_store(self, store) -> None:
        """Liga o spool cifrado da sessão (T-13.D4; envelopes v1 vão ao store)."""
        self._store = store

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

    def registrar_estado_reuniao(self, ativa: bool, agora: float | None = None, titulo: str | None = None) -> None:
        import time as _time

        agora = _time.monotonic() if agora is None else agora
        with self._estado_lock:
            self._reuniao_ativa = bool(ativa)
            self._visto_em = agora
            if titulo and isinstance(titulo, str) and len(titulo.strip()) >= 3:
                self._titulo_meet = titulo.strip()[:120]

    def titulo_meet_atual(self) -> str | None:
        with self._estado_lock:
            return self._titulo_meet

    def anexar_sessao(self, connection_id: str, session_id: str) -> None:
        """Vincula uma conexão à sessão consentida (T-13.D1; uma por aba)."""
        with self._estado_lock:
            self._sessao_por_conexao[str(connection_id)] = str(session_id)

    def desanexar_sessao(self, connection_id: str) -> None:
        with self._estado_lock:
            self._sessao_por_conexao.pop(str(connection_id), None)

    def sessao_de_conexao(self, connection_id: str) -> str | None:
        with self._estado_lock:
            return self._sessao_por_conexao.get(str(connection_id))

    def registrar_evento(self, dados: Any) -> None:
        if eh_evento_estado(dados):
            titulo = dados.get("titulo") if isinstance(dados, dict) else None
            self.registrar_estado_reuniao(estado_reuniao_do_evento(dados), titulo=titulo)
            return
        if isinstance(dados, dict) and "event_id" in dados and self._store is not None:
            try:
                self._store.append(dados)
            except Exception:  # noqa: BLE001 — EnvelopeRejeitado/ColetaBloqueada
                logger.debug("Envelope v1 fora da sessão; descartado.")
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

    def drenar_eventos(self, sessao_id: str | None = None) -> list[dict]:
        eventos: list[dict] = []
        while True:
            try:
                eventos.append(self.fila.get_nowait())
            except queue.Empty:
                break
        if sessao_id is None:
            return eventos
        return [ev for ev in eventos if ev.get("session_id") == sessao_id]

    def parar(self) -> None:
        self._parar.set()
        if self._loop and self._stop_future and not self._stop_future.done():
            self._loop.call_soon_threadsafe(self._stop_future.set_result, None)


async def _servidor_ws(bridge: MeetBridge, host: str, porta: int) -> None:
    import time as _time

    import websockets

    async def handler(websocket) -> None:
        origin = websocket.request.headers.get("Origin")
        if not origem_permitida(origin):
            await websocket.close(1008, "Origin not allowed")
            return
        token_url = _token_da_url(websocket.request.path or "")
        if bridge.pareador is not None:
            try:
                token_sessao, era_convite = bridge.pareador.autenticar(token_url)
            except ConviteInvalido:
                # Transição D2→D4: instalações antigas (token em config.js)
                # seguem válidas até o re-pareamento; novas usam o pareador.
                if not token_url_valido(token_url, bridge.token):
                    await websocket.close(1008, "Unauthorized")
                    return
                token_sessao, era_convite = bridge.token, False
            if era_convite:
                try:
                    await websocket.send(json.dumps({"tipo": "pareado", "token": token_sessao}))
                except Exception:  # noqa: BLE001
                    logger.debug("Falha ao entregar credencial de pareamento", exc_info=True)
                    return
        elif not token_url_valido(token_url, bridge.token):
            await websocket.close(1008, "Unauthorized")
            return
        with bridge._estado_lock:
            if bridge._conexoes_autenticadas >= MEET_WS_MAX_CONEXOES:
                overload = True
            else:
                overload = False
                bridge._conexoes_autenticadas += 1
        if overload:
            await websocket.close(1013, "Too many connections")
            return
        janela_saldo = float(MEET_WS_BURST)
        janela_ultima = _time.monotonic()
        try:
            async for mensagem in websocket:
                # Token bucket: rajada até BURST, sustentado EVENTOS_POR_SEG.
                # Excesso gera contador e descarte, nunca queda da conexão.
                agora = _time.monotonic()
                janela_saldo = min(
                    float(MEET_WS_BURST),
                    janela_saldo + (agora - janela_ultima) * MEET_WS_EVENTOS_POR_SEG,
                )
                janela_ultima = agora
                if janela_saldo < 1.0:
                    with bridge._estado_lock:
                        bridge.contador_descarte_rajada += 1
                    continue
                janela_saldo -= 1.0
                bridge.processar_mensagem(mensagem)
        except Exception:
            logger.debug("Cliente WebSocket desconectado", exc_info=True)
        finally:
            with bridge._estado_lock:
                bridge._conexoes_autenticadas = max(0, bridge._conexoes_autenticadas - 1)

    bridge._loop = asyncio.get_running_loop()
    bridge._stop_future = bridge._loop.create_future()
    async with websockets.serve(handler, host, porta, max_size=MEET_WS_MAX_BYTES):
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
    """Mantém `config.js` sem segredo (T-13.D2).

    O provisionamento agora é pelo pareamento de uso único (página
    `pairing.html` da extensão + `Pareador`); o content script não lê token.
    Este gerador preserva o arquivo como placeholder para não quebrar
    instalações antigas durante a transição.
    """
    del token
    caminho = os.path.join(base_dir, "extension", "meet", "config.js")
    conteudo = (
        "// Gerado automaticamente pelo Transkriptor — não editar manualmente.\n"
        "// T-13.D2: sem segredo aqui. Pareie pela página pairing.html da extensão.\n"
        'const MEET_WS_TOKEN = "";\n'
    )
    try:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except OSError:
        logger.warning("Não foi possível sincronizar token da extensão Meet.", exc_info=True)