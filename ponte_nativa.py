# -*- coding: utf-8 -*-
"""Host de Native Messaging `com.transkriptor.ponte` (T-15.E2 / FR-15.E2).

O Chrome/Edge só o executa para as extensões em `allowed_origins`. Ele atende
um único comando — `obter_codigo_pareamento` — e devolve um código `pair-` de
uso único que a ponte do Meet emite para quem apresenta o segredo local
(`config.ARQUIVO_SEGREDO_PONTE`, na pasta do usuário, trocado a cada início
do app). Não executa nada além disso; qualquer outra mensagem é recusada.

Protocolo (stdio): 4 bytes little-endian com o tamanho + JSON UTF-8.
"""
from __future__ import annotations

import json
import os
import struct
import sys
from urllib.parse import urlparse

import config

COMANDO = {"cmd": "obter_codigo_pareamento", "v": 1}
MENSAGEM_MAX = 64 * 1024


class AppDesligado(RuntimeError):
    """O app não está rodando, a ponte está desligada ou o segredo não confere."""


def ler_mensagem(entrada) -> object | None:
    cabecalho = entrada.read(4)
    if len(cabecalho) != 4:
        return None
    tamanho = struct.unpack("<I", cabecalho)[0]
    if tamanho > MENSAGEM_MAX:
        return None
    try:
        return json.loads(entrada.read(tamanho).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def escrever_mensagem(saida, mensagem: dict) -> None:
    corpo = json.dumps(mensagem).encode("utf-8")
    saida.write(struct.pack("<I", len(corpo)) + corpo)
    saida.flush()


def _origem_permitida(origem: str | None) -> bool:
    if not isinstance(origem, str):
        return False
    partes = urlparse(origem)
    return partes.scheme == "chrome-extension" and (partes.hostname or "") in config.EXTENSAO_IDS_PERMITIDOS


def publicar_segredo(segredo: str, porta: int) -> None:
    """Chamado pelo app ao subir a ponte: grava porta + segredo na pasta do usuário."""
    caminho = config.ARQUIVO_SEGREDO_PONTE
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    temporario = caminho + ".tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump({"porta": int(porta), "segredo": segredo}, arquivo)
    os.replace(temporario, caminho)


def obter_codigo_do_app(timeout_s: float = 5.0) -> tuple[str, int]:
    """Pede à ponte do Meet um código de pareamento com o segredo local."""
    try:
        with open(config.ARQUIVO_SEGREDO_PONTE, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        porta, segredo = int(dados["porta"]), str(dados["segredo"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AppDesligado("sem segredo da ponte") from exc
    from websockets.sync.client import connect

    try:
        with connect(f"ws://127.0.0.1:{porta}/?token={segredo}", origin="http://127.0.0.1",
                     open_timeout=timeout_s, close_timeout=1) as ws:
            resposta = json.loads(ws.recv(timeout=timeout_s))
    except Exception as exc:  # noqa: BLE001 — recusado, fechado ou fora do ar
        raise AppDesligado("ponte indisponível") from exc
    codigo = resposta.get("codigo") if isinstance(resposta, dict) and resposta.get("tipo") == "convite" else None
    if not isinstance(codigo, str) or not codigo.startswith("pair-"):
        raise AppDesligado("resposta inesperada da ponte")
    return codigo, porta


def atender(mensagem, origem: str | None, *, obter_codigo=obter_codigo_do_app) -> dict:
    if mensagem != COMANDO:
        return {"ok": False, "erro": "comando_invalido"}
    if not _origem_permitida(origem):
        return {"ok": False, "erro": "recusado"}
    try:
        codigo, porta = obter_codigo()
    except AppDesligado:
        return {"ok": False, "erro": "app_nao_iniciado"}
    return {"ok": True, "codigo": codigo, "porta": porta}


def main(argv: list[str]) -> int:
    # O Chrome passa a origem da extensão como primeiro argumento.
    origem = argv[1] if len(argv) > 1 else None
    resposta = atender(ler_mensagem(sys.stdin.buffer), origem)
    escrever_mensagem(sys.stdout.buffer, resposta)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
