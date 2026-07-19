# -*- coding: utf-8 -*-
"""Map-reduce de reuniões longas para o assistente (FR-4.3)."""
from __future__ import annotations

from collections.abc import Callable


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


def responder_longo(
    modelo: str,
    blocos: list[str],
    pergunta: str,
    chamar_ollama: Callable[[str, list[dict]], str],
) -> str:
    """Resume cada bloco e responde a pergunta sobre o conjunto."""
    resumos = []
    for i, bloco in enumerate(blocos, 1):
        msgs = [
            {
                "role": "system",
                "content": (
                    f"Resuma o trecho {i}/{len(blocos)} da reunião em português, "
                    "mantendo fatos, decisões e nomes."
                ),
            },
            {"role": "user", "content": bloco},
        ]
        resumos.append(chamar_ollama(modelo, msgs))
    consolidado = "\n\n".join(
        f"[Bloco {i}] {r}" for i, r in enumerate(resumos, 1)
    )
    msgs_final = [
        {
            "role": "system",
            "content": (
                "Você analisa resumos parciais de uma reunião longa. "
                "Responda em português com base nos blocos."
            ),
        },
        {
            "role": "user",
            "content": f"Resumos:\n{consolidado}\n\nPergunta: {pergunta}",
        },
    ]
    return chamar_ollama(modelo, msgs_final)
