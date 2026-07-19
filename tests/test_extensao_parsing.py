# -*- coding: utf-8 -*-
"""Parsing de legendas da extensão Meet (FR-5.1, FR-5.4).

Sem runner JS: a lógica de extração é espelhada em Python
(`extrair_legendas_html`) e deve permanecer alinhada a
`extension/meet/content.js` → `extrairLegendas()`.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from meet_bridge import normalizar_evento, sanitizar_nome_participante

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "meet"
MAX_TEXTO = 500


class _CapturaElementos(HTMLParser):
    """Parser HTML minimalista: coleta tags com attrs e texto."""

    def __init__(self) -> None:
        super().__init__()
        self.elementos: list[dict] = []
        self._stack: list[dict] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        el = {
            "tag": tag,
            "attrs": d,
            "class": set((d.get("class") or "").split()),
            "text": "",
            "children": [],
        }
        if self._stack:
            self._stack[-1]["children"].append(el)
        else:
            self.elementos.append(el)
        self._stack.append(el)

    def handle_endtag(self, tag):
        if self._stack:
            self._stack.pop()

    def handle_data(self, data):
        if self._stack:
            self._stack[-1]["text"] += data


def _texto_limpo(el: dict) -> str:
    partes = [el.get("text") or ""]
    for c in el.get("children") or []:
        partes.append(_texto_limpo(c))
    return re.sub(r"\s+", " ", "".join(partes)).strip()


def _walk(el: dict):
    yield el
    for c in el.get("children") or []:
        yield from _walk(c)


def extrair_legendas_html(html: str) -> list[tuple[str, str]]:
    """Espelho Python de extrairLegendas() em content.js (FR-5.1).

    Camadas:
      1. data-caption-block + data-speaker-name + data-caption-text (região)
      2. data-self-name / data-speaker-name com texto irmão
      3. classes ofuscadas (.NWpY1d/.zs7s8d + .ygicle) — último recurso
    """
    parser = _CapturaElementos()
    parser.feed(html)
    roots = parser.elementos
    todos: list[dict] = []
    for r in roots:
        todos.extend(_walk(r))

    pares: list[tuple[str, str]] = []

    # Camada 1: blocos data-caption-block
    for el in todos:
        if el["attrs"].get("data-caption-block") is None:
            continue
        nome = ""
        texto = ""
        for c in el.get("children") or []:
            for node in _walk(c):
                if node["attrs"].get("data-speaker-name"):
                    nome = node["attrs"]["data-speaker-name"] or _texto_limpo(node)
                if node["attrs"].get("data-caption-text") is not None:
                    texto = _texto_limpo(node)
        if not nome:
            for c in el.get("children") or []:
                t = _texto_limpo(c)
                if t and not nome:
                    nome = t
                elif t and not texto:
                    texto = t
        if nome and texto:
            pares.append((nome.strip(), texto.strip()[:MAX_TEXTO]))

    if pares:
        return pares

    # Camada 2: data-self-name ou data-speaker-name + irmão com texto
    for el in todos:
        nome = el["attrs"].get("data-speaker-name") or el["attrs"].get("data-self-name")
        if not nome:
            continue
        # procura irmão com texto de legenda no mesmo pai — varremos todos
        # e emparelhamos com próximo elemento de texto distinto
        # (heurística: nome + texto curto após o nome)
        pass

    # Camada 3: classes Meet ofuscadas
    nomes_cls = {"NWpY1d", "zs7s8d"}
    texto_cls = {"ygicle", "VbkSUe"}
    # agrupa por pai implícito: sequências nome→texto no documento
    i = 0
    flat = todos
    while i < len(flat):
        el = flat[i]
        classes = el["class"]
        if classes & nomes_cls:
            nome = _texto_limpo(el)
            texto = ""
            for j in range(i + 1, min(i + 8, len(flat))):
                if flat[j]["class"] & texto_cls or (
                    flat[j]["class"] & {"ygicle"} or "ygicle" in flat[j]["class"]
                ):
                    texto = _texto_limpo(flat[j])
                    if texto and texto != nome:
                        break
                # também aceita div com classe ygicle parcial
                if "ygicle" in " ".join(flat[j]["class"]):
                    texto = _texto_limpo(flat[j])
                    if texto and texto != nome:
                        break
            if nome and texto and nome != texto:
                pares.append((nome.strip(), texto.strip()[:MAX_TEXTO]))
        i += 1

    if pares:
        return pares

    # Camada 2 fallback mais simples: data-self-name com texto no próprio nó é só nome
    return pares


def test_normalizar_evento_preserva_texto_sanitizado():
    """FR-5.4: normalizar_evento aceita texto opcional sanitizado."""
    ev = normalizar_evento(
        {
            "nome": "  Ana\x00 Silva ",
            "texto": "  Olá,\x01 mundo  ",
            "ts_ms": 1500,
            "tipo": "legenda",
        }
    )
    assert ev is not None
    assert ev["nome"] == sanitizar_nome_participante("  Ana\x00 Silva ")
    assert "\x01" not in ev["texto"]
    assert ev["texto"] == "Olá, mundo"
    assert ev["tipo"] == "legenda"
    assert ev["ts_sec"] == pytest.approx(1.5)


def test_normalizar_evento_sem_nome_descarta():
    """FR-5.4: sem nome o evento é descartado mesmo com texto."""
    assert normalizar_evento({"texto": "oi", "ts_ms": 1, "tipo": "legenda"}) is None
    assert normalizar_evento({"nome": "", "texto": "oi"}) is None


def test_normalizar_evento_texto_maior_que_500_truncado():
    """FR-5.4: texto de legenda truncado em 500 chars."""
    longo = "a" * 600
    ev = normalizar_evento({"nome": "Ana", "texto": longo, "ts_ms": 1, "tipo": "legenda"})
    assert ev is not None
    assert len(ev["texto"]) == 500


def test_normalizar_evento_sem_texto_ok():
    """Eventos de falante ativo (sem texto) continuam válidos."""
    ev = normalizar_evento({"nome": "Ana", "ts_ms": 100, "tipo": "ativo"})
    assert ev is not None
    assert "texto" not in ev or ev.get("texto") in (None, "")


def test_fixture_regiao_produz_pares_nome_texto():
    """FR-5.1: fixture de região ARIA → (nome, texto) esperados."""
    html = (FIXTURES / "legendas_regiao.html").read_text(encoding="utf-8")
    pares = extrair_legendas_html(html)
    assert ("Ana Silva", "Bom dia a todos na reunião") in pares
    assert ("Bruno Costa", "Vamos revisar o cronograma") in pares


def test_fixture_classes_produz_pares_nome_texto():
    """FR-5.1: fixture de classes ofuscadas → (nome, texto) esperados."""
    html = (FIXTURES / "legendas_classes.html").read_text(encoding="utf-8")
    pares = extrair_legendas_html(html)
    assert ("Maria Santos", "Precisamos fechar o escopo hoje") in pares
    assert ("Pedro Lima", "Concordo com a proposta") in pares


def test_content_js_tem_tipo_legenda_e_campo_texto():
    """Sanidade: content.js envia tipo legenda e campo texto (espelho documentado)."""
    js = Path(__file__).resolve().parents[1] / "extension" / "meet" / "content.js"
    src = js.read_text(encoding="utf-8")
    assert '"legenda"' in src
    assert "payload.texto" in src or "texto:" in src
    assert "extrairLegendas" in src
