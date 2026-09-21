# -*- coding: utf-8 -*-
"""Map-reduce de reuniões longas para o assistente (FR-4.3, T-13.F2)."""
from __future__ import annotations

from collections.abc import Callable

import config as _config


class Cancelado(RuntimeError):
    """Cancelamento cooperativo durante o map-reduce."""


def dividir_em_blocos(texto: str, tamanho: int) -> list[str]:
    """Divide texto em blocos ≤ tamanho, preferindo quebras de linha."""
    if tamanho <= 0:
        return [texto] if texto else []
    if len(texto) <= tamanho:
        return [texto] if texto else []
    linhas = texto.splitlines(keepends=True)
    blocos: list[str] = []
    atual: list[str] = []
    n = 0
    for linha in linhas:
        if n + len(linha) > tamanho and atual:
            blocos.append("".join(atual))
            atual = []
            n = 0
        if len(linha) > tamanho:
            # linha gigante: corta cru
            if atual:
                blocos.append("".join(atual))
                atual = []
                n = 0
            for i in range(0, len(linha), tamanho):
                pedaco = linha[i : i + tamanho]
                if len(pedaco) == tamanho:
                    blocos.append(pedaco)
                else:
                    atual = [pedaco]
                    n = len(pedaco)
            continue
        atual.append(linha)
        n += len(linha)
    if atual:
        blocos.append("".join(atual))
    return blocos


def _truncar(texto: str, teto: int) -> str:
    if len(texto) <= teto:
        return texto
    return texto[: max(0, teto - 20)] + "…[cortado no orçamento]"


def responder_longo(
    modelo: str,
    blocos: list[str],
    pergunta: str,
    chamar_ollama: Callable[[str, list[dict]], str],
    *,
    orcamento_chars: int | None = None,
    cancelado: Callable[[], bool] | None = None,
) -> str:
    """Map-reduce com orçamento por chamada, teto de rodadas e cancelamento.

    Cada chamada cabe no orçamento (conteúdo truncado com marca). O mapa
    cobre todos os blocos; o teto (`RESUMO_MAX_RODADAS`, `RESUMO_MAX_CHAMADAS`)
    limita só a redução recursiva — esgotado, devolve parcial sinalizado.
    Erro de bloco é estado (aborta com mensagem), nunca resumo a resumir.
    Fala é dado delimitado em mensagem própria; sem ferramentas, sem
    mudança de escopo por instrução embutida.
    """
    teto = max(200, int(orcamento_chars or _config.MAX_CHARS_TRANSCRICAO))
    max_rodadas = int(_config.RESUMO_MAX_RODADAS)
    max_reducao = int(_config.RESUMO_MAX_CHAMADAS)

    def _checar_cancelado() -> None:
        if cancelado is not None and cancelado():
            raise Cancelado("map-reduce cancelado")

    def _chamar(sistema: str, conteudo: str) -> str:
        _checar_cancelado()
        margem = len(sistema) + 60
        msgs = [
            {"role": "system", "content": sistema},
            {"role": "user", "content": _truncar(conteudo, max(50, teto - margem))},
        ]
        try:
            saida = chamar_ollama(modelo, msgs)
        except Cancelado:
            raise
        except Exception as exc:
            raise RuntimeError(f"falha no bloco: {exc}") from exc
        if isinstance(saida, str) and saida.startswith("[Erro"):
            raise RuntimeError(f"falha no bloco: {saida[:80]}")
        return saida if isinstance(saida, str) else str(saida)

    pergunta_corta = _truncar(str(pergunta or ""), teto)
    try:
        resumos = [
            _chamar(
                f"Resuma o trecho {i}/{len(blocos)} da reunião em português, "
                "mantendo fatos, decisões e nomes.",
                texto,
            )
            for i, texto in enumerate(list(blocos), 1)
        ]
        consolidado = "\n\n".join(f"[Bloco {i}] {r}" for i, r in enumerate(resumos, 1))
        rodada = 0
        usadas = 0
        while len(consolidado) > teto and rodada < max_rodadas:
            partes = dividir_em_blocos(consolidado, teto)
            if len(partes) <= 1 or usadas + len(partes) > max_reducao:
                consolidado = _truncar(consolidado, teto) + "\n[map-reduce truncado no teto]"
                break
            resumos = [
                _chamar(
                    "Você analisa resumos parciais de uma reunião longa. "
                    "Condense em português sem perder fatos.",
                    parte,
                )
                for parte in partes
            ]
            usadas += len(partes)
            consolidado = "\n\n".join(f"[Bloco {i}] {r}" for i, r in enumerate(resumos, 1))
            rodada += 1
        if len(consolidado) > teto:
            consolidado = _truncar(consolidado, teto) + "\n[map-reduce truncado no teto]"
        return _chamar(
            "Você analisa resumos parciais de uma reunião longa. "
            "Responda em português com base nos blocos.",
            f"Resumos:\n{consolidado}\n\nPergunta: {pergunta_corta}",
        )
    except Cancelado:
        raise
    except RuntimeError as exc:
        return f"[Erro ao processar reunião longa: {exc}]"
