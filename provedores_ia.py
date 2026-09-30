# -*- coding: utf-8 -*-
"""Provedores de IA para resumo e chat (T-15.D1 / FR-15.D1).

Um só caminho até o Ollama: listar modelos, estado, contexto e conversa
(síncrona ou em stream). A URL vem de `config_user.ollama_url`, depois de
`OLLAMA_HOST`, depois de `config.OLLAMA_URL` — e só pode ser loopback
(DP-15-09). Erros viram `ErroProvedor` com mensagem sem conteúdo da conversa.

`urllib.request.urlopen` é resolvido na hora da chamada: os testes o
substituem pelo módulo global.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import urlparse

import config as _config

LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
PORTA_OLLAMA = 11434


class ErroProvedor(RuntimeError):
    """Falha do provedor; `mensagem_segura` nunca traz texto da conversa nem chave."""

    def __init__(self, codigo: str, mensagem_segura: str) -> None:
        super().__init__(mensagem_segura)
        self.codigo = codigo
        self.mensagem_segura = mensagem_segura


@dataclass(frozen=True)
class ModeloIA:
    id: str
    nome: str
    tamanho_bytes: int | None = None
    contexto: int | None = None
    local: bool = True


@dataclass(frozen=True)
class EstadoProvedor:
    estado: str  # online | offline | sem_modelos | sem_chave | chave_invalida
    detalhe: str = ""
    versao: str | None = None


def normalizar_url_ollama(bruto: str) -> str:
    """`host:porta` ou URL → `http://host:porta`; fora do loopback é recusada."""
    texto = str(bruto or "").strip().rstrip("/")
    if not texto:
        raise ValueError("URL do Ollama vazia")
    if "://" not in texto:
        texto = "http://" + texto
    partes = urlparse(texto)
    host = (partes.hostname or "").lower()
    if host == "0.0.0.0":  # OLLAMA_HOST=0.0.0.0 escuta em tudo; o app conecta pelo loopback
        host = "127.0.0.1"
    if host not in LOOPBACK:
        raise ValueError("o Ollama só pode ser acessado neste computador (DP-15-09)")
    porta = partes.port or PORTA_OLLAMA
    return f"http://{'[::1]' if host == '::1' else host}:{porta}"


def url_ollama() -> str:
    """Primeira URL válida entre configuração do usuário, OLLAMA_HOST e padrão."""
    import config_user

    candidatos = (config_user.carregar().get("ollama_url"), os.environ.get("OLLAMA_HOST"), _config.OLLAMA_URL)
    for candidato in candidatos:
        if isinstance(candidato, str) and candidato.strip():
            try:
                return normalizar_url_ollama(candidato)
            except ValueError:
                continue
    return f"http://127.0.0.1:{PORTA_OLLAMA}"


def _conteudos_ndjson(bruto: str) -> str:
    """O Ollama pode responder em NDJSON mesmo com stream=False: junta os pedaços."""
    partes = []
    for linha in bruto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        bloco = json.loads(linha)
        partes.append((bloco.get("message") or {}).get("content") or "")
    return "".join(partes)


class ProvedorOllama:
    id = "ollama"

    def __init__(self, url: str | None = None) -> None:
        self._url = normalizar_url_ollama(url) if url else None
        self._contextos: dict[str, int] = {}

    @property
    def url(self) -> str:
        return self._url or url_ollama()

    def _get(self, caminho: str, timeout: float) -> dict:
        with urllib.request.urlopen(self.url + caminho, timeout=timeout) as resposta:
            return json.loads(resposta.read().decode("utf-8"))

    def _pedido(self, caminho: str, corpo: dict) -> urllib.request.Request:
        return urllib.request.Request(
            self.url + caminho, data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )

    def versao(self, timeout: float | None = None) -> str | None:
        return self._get("/api/version", timeout or _config.OLLAMA_TIMEOUT_CONEXAO).get("version")

    def listar_modelos(self, timeout: float | None = None) -> list[ModeloIA]:
        try:
            dados = self._get("/api/tags", timeout or _config.OLLAMA_TIMEOUT_CONEXAO)
        except Exception:  # noqa: BLE001 — fora do ar: nenhum modelo
            return []
        return [
            ModeloIA(m["name"], m["name"], m.get("size") if isinstance(m.get("size"), int) else None)
            for m in dados.get("models", []) if isinstance(m, dict) and m.get("name")
        ]

    def estado(self) -> EstadoProvedor:
        try:
            versao = self.versao()
        except Exception:  # noqa: BLE001
            return EstadoProvedor("offline", "O Ollama não respondeu neste computador.")
        return EstadoProvedor("online" if self.listar_modelos() else "sem_modelos", "", versao)

    def contexto(self, modelo: str) -> int | None:
        """Janela de contexto do modelo (/api/show); None se não der para saber."""
        if modelo in self._contextos:
            return self._contextos[modelo]
        try:
            with urllib.request.urlopen(self._pedido("/api/show", {"name": modelo}),
                                        timeout=_config.OLLAMA_TIMEOUT_LEITURA) as resposta:
                dados = json.loads(resposta.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None
        for chave, valor in (dados.get("model_info") or {}).items():
            if "context_length" in str(chave).lower() and isinstance(valor, (int, float)):
                self._contextos[modelo] = int(valor)
                return self._contextos[modelo]
        for parte in str(dados.get("parameters") or "").split():
            if parte.isdigit() and int(parte) >= 512:
                self._contextos[modelo] = int(parte)
                return self._contextos[modelo]
        return None

    def _corpo(self, mensagens, modelo, opcoes, pensar, stream) -> dict:
        corpo = {"model": modelo, "messages": list(mensagens), "stream": stream}
        if opcoes:
            corpo["options"] = dict(opcoes)
        if pensar is not None:
            corpo["think"] = bool(pensar)
        return corpo

    def conversar(self, mensagens, *, modelo: str, opcoes: dict | None = None, pensar: bool | None = None,
                  timeout: float | None = None) -> str:
        pedido = self._pedido("/api/chat", self._corpo(mensagens, modelo, opcoes, pensar, False))
        try:
            with urllib.request.urlopen(pedido, timeout=timeout or _config.OLLAMA_TIMEOUT_LEITURA) as resposta:
                return _conteudos_ndjson(resposta.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ErroProvedor("indisponivel", f"Erro ao contatar o Ollama: {type(exc).__name__}") from exc

    def conversar_stream(self, mensagens, *, modelo: str, opcoes: dict | None = None,
                         timeout: float | None = None) -> Iterator[str]:
        pedido = self._pedido("/api/chat", self._corpo(mensagens, modelo, opcoes, None, True))
        try:
            resposta = urllib.request.urlopen(pedido, timeout=timeout or _config.OLLAMA_TIMEOUT_LEITURA)
        except Exception as exc:  # noqa: BLE001
            raise ErroProvedor("indisponivel", f"Erro ao contatar o Ollama: {type(exc).__name__}") from exc
        try:
            for linha in resposta:
                linha = linha.decode("utf-8").strip() if isinstance(linha, bytes) else str(linha).strip()
                if not linha:
                    continue
                try:
                    bloco = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                conteudo = (bloco.get("message") or {}).get("content") or ""
                if conteudo:
                    yield conteudo
                if bloco.get("done"):
                    break
        finally:
            try:
                resposta.close()
            except Exception:  # noqa: BLE001
                pass


def provedor_ollama() -> ProvedorOllama:
    """Provedor local com a URL configurada no momento da chamada."""
    return ProvedorOllama()


def provedor_para(funcao: str):
    """Provedor escolhido para "resumo" ou "chat" (T-15.D2). OpenRouter só com
    chave e consentimento; sem eles, erro explícito — nunca troca sozinho."""
    import config_user

    cfg = config_user.carregar()
    if cfg.get(f"ia_{funcao}_provedor") == "openrouter":
        from provedor_openrouter import ProvedorOpenRouter, chave

        if not cfg.get("openrouter_consentido_em"):
            raise ErroProvedor("sem_consentimento", "Autorize o uso do OpenRouter nas Configurações.")
        return ProvedorOpenRouter(chave())
    return ProvedorOllama()
