#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera docs/MANUAL-USUARIO.pdf a partir do Markdown."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from config import VERSAO

MD_PATH = REPO / "docs" / "MANUAL-USUARIO.md"
PDF_PATH = REPO / "docs" / "MANUAL-USUARIO.pdf"


def _ascii_safe(text: str) -> str:
    """fpdf core font: substitui chars fora de latin-1."""
    substituicoes = {
        "✓": "[OK]",
        "—": "-",
        "…": "...",
        "«": '"',
        "»": '"',
        "→": "->",
        "↔": "<->",
        "≥": ">=",
        "≤": "<=",
        "├──": "+--",
        "└──": "`--",
        "│": "|",
    }
    for k, v in substituicoes.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _limpar_markdown(text: str) -> str:
    text = re.sub(r"\[([^]]+)]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    return re.sub(r"`(.+?)`", r"\1", text)


def md_para_linhas(md: str) -> list[tuple[str, str]]:
    """Retorna lista (estilo, texto): h1, h2, h3, bullet, body, sep."""
    linhas: list[tuple[str, str]] = []
    in_code = False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            linhas.append(("code", line))
            continue
        if line.startswith("# "):
            linhas.append(("h1", line[2:].strip()))
        elif line.startswith("## "):
            linhas.append(("h2", line[3:].strip()))
        elif line.startswith("### "):
            linhas.append(("h3", line[4:].strip()))
        elif line.startswith("|") and "|" in line[1:]:
            linhas.append(("table", line))
        elif line.startswith("- ") or line.startswith("* "):
            linhas.append(("bullet", line[2:].strip()))
        elif line.strip() == "---":
            linhas.append(("sep", ""))
        elif line.strip():
            linhas.append(("body", line.strip()))
    return linhas


def extrair_texto_pdf(pdf_path: Path) -> str:
    """Extrai texto de todas as páginas (validação de legibilidade)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf", "-q"])
        from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    partes = []
    for pagina in reader.pages:
        partes.append(pagina.extract_text() or "")
    return "\n".join(partes)


def validar_pdf_legivel(pdf_path: Path, min_chars: int = 2500) -> dict:
    """Confirma PDF com texto extraível on-page (pós-fix LMARGIN)."""
    texto = extrair_texto_pdf(pdf_path).strip()
    marcadores = ("Transkriptor", "Bandeja", "Diariz", "Segur")
    encontrados = [m for m in marcadores if m.lower() in texto.lower()]
    return {
        "chars": len(texto),
        "marcadores": encontrados,
        "ok": len(texto) >= min_chars and len(encontrados) >= 3,
    }


def gerar_pdf(md_path: Path = MD_PATH, pdf_path: Path = PDF_PATH) -> Path:
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "fpdf2", "-q"])
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos

    if not md_path.is_file():
        raise FileNotFoundError(md_path)

    conteudo = md_path.read_text(encoding="utf-8")
    itens = md_para_linhas(conteudo)

    class ManualPDF(FPDF):
        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "I", 8)
            self.set_x(self.l_margin)
            self.cell(
                0,
                8,
                f"Transkriptor v{VERSAO} - Manual do Usuario - Pagina {self.page_no()}/{{nb}}",
                align="C",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

    pdf = ManualPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(15, 15, 18)
    epw = pdf.w - pdf.l_margin - pdf.r_margin

    def escrever(texto: str, h: float, font=("Helvetica", "", 10)) -> None:
        pdf.set_font(*font)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            epw,
            h,
            texto,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    for estilo, texto in itens:
        if estilo != "code":
            texto = _limpar_markdown(texto)
        texto = _ascii_safe(texto)
        if estilo == "h1":
            pdf.ln(4)
            escrever(texto, 8, ("Helvetica", "B", 16))
            pdf.ln(2)
        elif estilo == "h2":
            pdf.ln(3)
            escrever(texto, 7, ("Helvetica", "B", 13))
            pdf.ln(1)
        elif estilo == "h3":
            escrever(texto, 6, ("Helvetica", "B", 11))
        elif estilo == "bullet":
            escrever(f"- {texto}", 5)
        elif estilo == "code":
            escrever(f"  {texto}", 4, ("Courier", "", 8))
        elif estilo == "table":
            if re.match(r"^\|[-:| ]+\|$", texto):
                continue
            celulas = [c.strip() for c in texto.strip("|").split("|") if c.strip()]
            if len(celulas) >= 2:
                escrever(f"{celulas[0]}: {celulas[1]}", 4, ("Helvetica", "", 9))
            else:
                escrever(texto.replace("|", " "), 4, ("Helvetica", "", 9))
        elif estilo == "sep":
            pdf.ln(2)
            pdf.set_draw_color(180, 180, 180)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.set_x(pdf.l_margin)
            pdf.ln(3)
        else:
            escrever(texto, 5)

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(pdf_path))
    return pdf_path


if __name__ == "__main__":
    out = gerar_pdf()
    size = out.stat().st_size
    validacao = validar_pdf_legivel(out)
    print(f"PDF gerado: {out} ({size} bytes)")
    print(f"Texto extraível: {validacao['chars']} chars, marcadores: {validacao['marcadores']}")
    if size < 10_240:
        print("AVISO: PDF menor que 10 KB", file=sys.stderr)
        sys.exit(1)
    if not validacao["ok"]:
        print("AVISO: PDF sem texto legível suficiente on-page", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
