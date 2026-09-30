# -*- coding: utf-8 -*-
"""Pacote da extensão para a Chrome Web Store / Edge Add-ons (T-15.E5 / FR-15.E5).

Zip determinístico (ordem e datas fixas) só com o que a extensão executa:
sem a `key` de desenvolvimento (a loja atribui a própria), sem README, textos
da loja nem restos antigos. A versão tem de ser a do produto (`config.VERSAO`).

    python scripts/empacotar_extensao.py [destino.zip]
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

PASTA = RAIZ / "extension" / "meet"
FORA = {"README.md", "LOJA.md", "config.js"}  # config.js: resto do token legado, sem uso
DATA_FIXA = (2026, 1, 1, 0, 0, 0)


def _arquivos() -> list[Path]:
    return sorted(
        p for p in PASTA.rglob("*")
        if p.is_file() and p.name not in FORA and not p.name.startswith(".")
        and not p.name.endswith((".test.js", ".map"))
    )


def empacotar(destino: Path) -> Path:
    import config

    manifesto = json.loads((PASTA / "manifest.json").read_text(encoding="utf-8"))
    if manifesto.get("version") != config.VERSAO:
        raise ValueError(f"versão do manifest ({manifesto.get('version')}) difere de config.VERSAO ({config.VERSAO})")
    manifesto.pop("key", None)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for caminho in _arquivos():
            relativo = caminho.relative_to(PASTA).as_posix()
            dados = (json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n").encode("utf-8") \
                if relativo == "manifest.json" else caminho.read_bytes()
            info = zipfile.ZipInfo(relativo, DATA_FIXA)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, dados)
    return destino


if __name__ == "__main__":
    import config

    alvo = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "dist" / f"transkriptor-meet-{config.VERSAO}.zip"
    print(f"Pacote da extensão: {empacotar(alvo)}")
