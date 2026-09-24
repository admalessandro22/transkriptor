# -*- coding: utf-8 -*-
"""UX-14.A1 — tokens de design em fonte única (T-14.A1).

Cobre: sincronia JSON → CSS/Python, contraste AA em ambos os temas, ausência
de cor literal fora de `tokens.css` e o ícone da bandeja consumindo os mesmos
valores. Não importa a bandeja nem inicializa recursos de produção.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TOKENS = REPO / "design" / "tokens.json"
CSS_TOKENS = REPO / "static" / "css" / "tokens.css"
PY_TOKENS = REPO / "design_tokens.py"
GERADOR = REPO / "scripts" / "gerar_tokens.py"


def _gerador():
    spec = importlib.util.spec_from_file_location("gerar_tokens", GERADOR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def gerador():
    return _gerador()


@pytest.fixture(scope="module")
def tokens(gerador):
    return gerador.carregar_tokens(TOKENS)


def test_css_gerado_igual_ao_disco(gerador, tokens):
    assert CSS_TOKENS.is_file(), "static/css/tokens.css ausente; rode gerar_tokens.py --write"
    assert CSS_TOKENS.read_text(encoding="utf-8") == gerador.gerar_css(tokens)


def test_python_gerado_igual_ao_disco(gerador, tokens):
    assert PY_TOKENS.is_file(), "design_tokens.py ausente; rode gerar_tokens.py --write"
    assert PY_TOKENS.read_text(encoding="utf-8") == gerador.gerar_python(tokens)


def test_todos_pares_contraste_aa(gerador, tokens):
    assert tokens["contrast_pairs"], "tokens.json precisa declarar pares de contraste"
    assert gerador.verificar_contraste(tokens) == []


def test_css_tem_dois_temas_e_prefixo_tk(gerador, tokens):
    css = gerador.gerar_css(tokens)
    assert "color-scheme: dark light" in css
    assert "@media (prefers-color-scheme: light)" in css
    assert ':root[data-theme="light"]' in css
    assert "--tk-bg-1:" in css and "--tk-accent:" in css and "--tk-state-recording:" in css
    assert "--tk-dur-fast: 120ms" in css and "bounce" not in css


_COR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", re.IGNORECASE)


def _valores_de_propriedade(css: str) -> str:
    """Só o interior das chaves: seletores como `#chat` não contam."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return "\n".join(m.group(1) for m in re.finditer(r"\{([^{}]*)\}", css))


def test_sem_hex_fora_de_tokens_css():
    arquivos = [p for p in REPO.glob("static/**/*.css") if p.name != "tokens.css"]
    assert arquivos, "nenhum CSS de produto encontrado"
    ofensas = []
    for arquivo in arquivos:
        for numero, linha in enumerate(
            _valores_de_propriedade(arquivo.read_text(encoding="utf-8")).splitlines(), 1
        ):
            if "data:image" in linha:
                continue
            if _COR_LITERAL.search(linha):
                ofensas.append(f"{arquivo.relative_to(REPO)}: {linha.strip()[:80]}")
    assert not ofensas, "cor literal fora de tokens.css:\n" + "\n".join(ofensas[:20])


def test_estado_icone_usa_design_tokens():
    fonte = (REPO / "estado_icone.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    importados: set[str] = set()
    atribuicoes_literais: list[str] = []
    for no in arvore.body:
        if isinstance(no, ast.ImportFrom) and no.module == "design_tokens":
            importados.update(alias.name for alias in no.names)
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id.startswith("COR_") and isinstance(no.value, ast.Tuple):
                    atribuicoes_literais.append(alvo.id)
    esperadas = {"COR_AGUARDANDO", "COR_TRANSCREVENDO", "COR_DIARIZANDO", "COR_PROCESSANDO", "COR_ERRO", "COR_PAUSADO"}
    assert esperadas <= importados, f"estado_icone não importa de design_tokens: {esperadas - importados}"
    assert not atribuicoes_literais, f"cores literais em estado_icone: {atribuicoes_literais}"


def test_cores_do_icone_iguais_ao_json(tokens):
    spec = importlib.util.spec_from_file_location("design_tokens_teste", PY_TOKENS)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    for constante, chave in tokens["estado_icone"].items():
        hexa = tokens["color"]["state"][chave].lstrip("#")
        esperado = tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))
        assert getattr(modulo, constante) == esperado
    assert modulo.COR_PAUSADO == (100, 116, 139)  # compatibilidade com test_transkiptor_estado


def test_check_reprova_json_alterado_sem_regenerar(tmp_path: Path):
    dados = json.loads(TOKENS.read_text(encoding="utf-8"))
    dados["color"]["dark"]["text-1"] = "#E0E0E0"
    alterado = tmp_path / "tokens.json"
    alterado.write_text(json.dumps(dados), encoding="utf-8")
    resultado = subprocess.run(
        [sys.executable, str(GERADOR), "--check", "--tokens", str(alterado)],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8",
    )
    assert resultado.returncode == 1
    assert "DESATUALIZADOS" in resultado.stderr


def test_write_recusa_par_abaixo_do_minimo(tmp_path: Path):
    dados = json.loads(TOKENS.read_text(encoding="utf-8"))
    dados["color"]["dark"]["text-3"] = "#2A2E38"  # quase igual ao fundo
    alterado = tmp_path / "tokens.json"
    alterado.write_text(json.dumps(dados), encoding="utf-8")
    resultado = subprocess.run(
        [sys.executable, str(GERADOR), "--write", "--tokens", str(alterado),
         "--css", str(tmp_path / "t.css"), "--py", str(tmp_path / "t.py")],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8",
    )
    assert resultado.returncode == 1
    assert "CONTRASTE REPROVADO" in resultado.stderr
    assert not (tmp_path / "t.css").exists()
