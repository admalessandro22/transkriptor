# -*- coding: utf-8 -*-
"""OpenRouter como provedor opcional de resumo e chat (T-15.D2 / SEC-15.D2).

Só por escolha do usuário (DP-15-04): a chave fica cifrada por DPAPI e nunca
volta ao front; o uso exige consentimento registrado; toda saída remota é
marcada; áudio e voz nunca saem. Pede que o roteamento negue coleta de
dados e use retenção zero (`provider.data_collection="deny"`, `zdr=true`),
conforme a documentação do OpenRouter consultada em 29/09/2026.
"""
from __future__ import annotations

import datetime
import json
import urllib.error
import urllib.request
from typing import Iterator

import config as _config
from provedores_ia import ErroProvedor, EstadoProvedor, ModeloIA

BASE = "https://openrouter.ai/api/v1"
TITULO = "Transkriptor"
PREFERENCIA_PROVEDOR = {"data_collection": "deny", "zdr": True}
TEXTO_CONSENTIMENTO = (
    "Ao usar o OpenRouter, o texto da transcrição e as suas perguntas saem deste computador "
    "e vão para o OpenRouter e o provedor do modelo escolhido. Áudio e voz nunca saem. "
    "Cada resposta mostrará que foi gerada pelo OpenRouter."
)


def chave() -> str | None:
    import config_user
    from crypto_storage import revelar_segredo

    cifrada = config_user.carregar().get("openrouter_chave_dpapi")
    if not isinstance(cifrada, str) or not cifrada:
        return None
    try:
        return revelar_segredo(cifrada)
    except Exception:  # noqa: BLE001 — outra conta/máquina: como se não houvesse chave
        return None


def chave_final() -> str | None:
    valor = chave()
    return valor[-4:] if valor else None


def salvar_chave(valor: str) -> None:
    import config_user
    from crypto_storage import proteger_segredo

    valor = str(valor or "").strip()
    if not valor or len(valor) > 200 or any(c.isspace() for c in valor):
        raise ValueError("chave do OpenRouter inválida")
    config_user.atualizar(openrouter_chave_dpapi=proteger_segredo(valor))


def consentir() -> str:
    import config_user

    quando = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    config_user.atualizar(openrouter_consentido_em=quando)
    return quando


def _erro(exc: Exception) -> ErroProvedor:
    if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403):
        return ErroProvedor("chave_invalida", "A chave do OpenRouter foi recusada. Confira nas Configurações.")
    if isinstance(exc, urllib.error.HTTPError) and exc.code == 402:
        return ErroProvedor("sem_credito", "O OpenRouter recusou por falta de créditos.")
    return ErroProvedor("indisponivel", f"Erro ao contatar o OpenRouter: {type(exc).__name__}")


class ProvedorOpenRouter:
    id = "openrouter"

    def __init__(self, chave_api: str | None) -> None:
        if not chave_api:
            raise ErroProvedor("sem_chave", "Informe a chave do OpenRouter nas Configurações.")
        self._chave = chave_api
        self._contextos: dict[str, int] = {}

    def _pedido(self, caminho: str, corpo: dict | None = None) -> urllib.request.Request:
        cabecalhos = {"Authorization": f"Bearer {self._chave}", "X-OpenRouter-Title": TITULO}
        dados = None
        if corpo is not None:
            cabecalhos["Content-Type"] = "application/json"
            dados = json.dumps(corpo).encode("utf-8")
        return urllib.request.Request(BASE + caminho, data=dados, headers=cabecalhos,
                                      method="POST" if corpo is not None else "GET")

    def _json(self, pedido, timeout) -> dict:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            return json.loads(resposta.read().decode("utf-8"))

    def estado(self) -> EstadoProvedor:
        try:
            self._json(self._pedido("/key"), _config.OLLAMA_TIMEOUT_CONEXAO)
        except Exception as exc:  # noqa: BLE001
            erro = _erro(exc)
            return EstadoProvedor("chave_invalida" if erro.codigo == "chave_invalida" else "offline",
                                  erro.mensagem_segura)
        return EstadoProvedor("online")

    def listar_modelos(self) -> list[ModeloIA]:
        try:
            dados = self._json(self._pedido("/models"), _config.OLLAMA_TIMEOUT_LEITURA)
        except Exception:  # noqa: BLE001
            return []
        modelos = []
        for m in dados.get("data", []):
            if not isinstance(m, dict) or not isinstance(m.get("id"), str):
                continue
            contexto = m.get("context_length") if isinstance(m.get("context_length"), int) else None
            if contexto:
                self._contextos[m["id"]] = contexto
            modelos.append(ModeloIA(m["id"], str(m.get("name") or m["id"]), None, contexto, False))
        return modelos

    def contexto(self, modelo: str) -> int | None:
        if modelo not in self._contextos:
            self.listar_modelos()
        return self._contextos.get(modelo)

    def _corpo(self, mensagens, modelo, opcoes, stream) -> dict:
        corpo = {"model": modelo, "messages": list(mensagens), "stream": stream,
                 "provider": dict(PREFERENCIA_PROVEDOR)}
        for chave_opcao in ("temperature", "max_tokens"):  # num_ctx é coisa do Ollama
            if opcoes and chave_opcao in opcoes:
                corpo[chave_opcao] = opcoes[chave_opcao]
        return corpo

    def conversar(self, mensagens, *, modelo: str, opcoes: dict | None = None, pensar: bool | None = None,
                  timeout: float | None = None) -> str:
        del pensar  # sem equivalente estável entre modelos do OpenRouter
        try:
            dados = self._json(self._pedido("/chat/completions", self._corpo(mensagens, modelo, opcoes, False)),
                               timeout or _config.OLLAMA_TIMEOUT_LEITURA)
        except Exception as exc:  # noqa: BLE001
            raise _erro(exc) from exc
        escolhas = dados.get("choices") or [{}]
        return ((escolhas[0] or {}).get("message") or {}).get("content") or ""

    def conversar_stream(self, mensagens, *, modelo: str, opcoes: dict | None = None,
                         timeout: float | None = None) -> Iterator[str]:
        pedido = self._pedido("/chat/completions", self._corpo(mensagens, modelo, opcoes, True))
        try:
            resposta = urllib.request.urlopen(pedido, timeout=timeout or _config.OLLAMA_TIMEOUT_LEITURA)
        except Exception as exc:  # noqa: BLE001
            raise _erro(exc) from exc
        try:
            for linha in resposta:
                linha = linha.decode("utf-8").strip() if isinstance(linha, bytes) else str(linha).strip()
                if not linha.startswith("data:"):
                    continue  # comentários de keep-alive (": OPENROUTER PROCESSING")
                dado = linha[5:].strip()
                if dado == "[DONE]":
                    break
                try:
                    bloco = json.loads(dado)
                except json.JSONDecodeError:
                    continue
                conteudo = (((bloco.get("choices") or [{}])[0] or {}).get("delta") or {}).get("content") or ""
                if conteudo:
                    yield conteudo
        finally:
            try:
                resposta.close()
            except Exception:  # noqa: BLE001
                pass
