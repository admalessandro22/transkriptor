# -*- coding: utf-8 -*-
"""NFR-14.G1 — manual com todas as superfícies, capturas sintéticas e glossário (T-14.G1)."""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANUAL = REPO / "docs" / "MANUAL-USUARIO.md"
CAPTURAS = REPO / "docs" / "manual" / "capturas"

SUPERFICIES = {
    "bandeja": ("bandeja-icones.png",),
    "consentimento": ("consentimento-100pct.png", "consentimento-200pct.png"),
    "confirmação": ("confirmacao-bandeja.png", "confirmacao-central-dark.png", "confirmacao-central-light.png"),
    "início": ("central-inicio-dark.png", "central-inicio-light.png"),
    "reuniões": ("central-reunioes-dark.png", "central-reunioes-light.png"),
    "assistente": ("central-assistente-dark.png", "central-assistente-light.png"),
    "participantes": ("central-participantes-dark.png", "central-participantes-light.png"),
    "configurações": ("central-configuracoes-dark.png", "central-configuracoes-light.png"),
    "diagnóstico": ("central-diagnostico-dark.png", "central-diagnostico-light.png"),
    "pareamento": ("extensao-pareamento-dark.png", "extensao-pareamento-light.png"),
}
GLOSSARIO_DESIGN = ("Reunião", "Transcrição", "Falante", "Participante", "VOCÊ", "Identificação pendente", "Sugestão", "Protegida", "Legível", "Separar vozes")
NOMES_FIXTURES = ("Ana Souza",)
# Nomes que nunca podem aparecer: pessoas reais do ambiente de desenvolvimento.
NOMES_PROIBIDOS = ("Alessandro", "meirelesefreitas")


def _texto() -> str:
    return MANUAL.read_text(encoding="utf-8")


def test_manual_referencia_todas_as_superficies():
    texto = _texto()
    baixo = texto.lower()
    for superficie, arquivos in SUPERFICIES.items():
        assert superficie in baixo, f"manual não fala de {superficie}"
        for arquivo in arquivos:
            assert f"manual/capturas/{arquivo}" in texto, f"manual não referencia {arquivo}"
    assert "## 7. A Central" in texto
    for pagina in ("Início", "Reuniões", "Assistente", "Participantes", "Configurações", "Diagnóstico"):
        assert f"### {pagina}" in texto or f"### 7." in texto and pagina in texto


def test_capturas_existem_e_sao_sinteticas():
    texto = _texto()
    referencias = re.findall(r"\]\((?:\.\./)?(?:docs/)?manual/capturas/([^)]+\.png)\)", texto)
    assert referencias, "nenhuma captura referenciada"
    for nome in referencias:
        assert (CAPTURAS / nome).is_file(), f"captura ausente: {nome}"
    esperadas = {a for arquivos in SUPERFICIES.values() for a in arquivos}
    assert esperadas <= set(referencias)
    manifesto = (CAPTURAS / "README.md").read_text(encoding="utf-8")
    for nome in esperadas:
        assert nome in manifesto, f"manifesto sem origem de {nome}"
    assert "sintétic" in manifesto.lower()
    for nome in NOMES_FIXTURES:
        assert nome in texto, "o manual deve apresentar os exemplos com os nomes das fixtures"
    for proibido in NOMES_PROIBIDOS:
        assert proibido.lower() not in texto.lower() and proibido.lower() not in manifesto.lower()


def test_glossario_cobre_o_design_system():
    texto = _texto()
    glossario = texto.split("## 13. Glossário")[1]
    for termo in GLOSSARIO_DESIGN:
        assert termo in glossario, f"glossário sem {termo}"
    for estado in ("Aguardando reunião", "Gravando", "Processando reunião", "Separando vozes", "Pausado", "Erro"):
        assert estado in glossario, estado


def test_manual_sem_vocabulario_antigo():
    texto = _texto()
    assert "Abrir assistente (resumo, perguntas)" not in texto
    assert "dropdown" not in texto.lower()
    assert "PAUSADO — não está gravando" not in texto
    assert "Transcrevendo" not in texto
