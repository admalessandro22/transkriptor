# -*- coding: utf-8 -*-
"""Registra o host de Native Messaging para o usuário atual (T-15.E2).

Cria o lançador e o manifesto em `%LOCALAPPDATA%\\Transkriptor\\native` e aponta
as chaves HKCU do Chrome e do Edge para ele. Sem administrador. `desregistrar`
desfaz. Uso: `python -m instalador.registrar_host [--remover]`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

NOME = "com.transkriptor.ponte"
CHAVES = (
    rf"Software\Google\Chrome\NativeMessagingHosts\{NOME}",
    rf"Software\Microsoft\Edge\NativeMessagingHosts\{NOME}",
)
RAIZ_APP = Path(__file__).resolve().parent.parent


def _destino_padrao() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Transkriptor" / "native"


def _escrever_registro(chave: str, valor: str) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chave) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, valor)


def _apagar_registro(chave: str) -> None:
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, chave)
    except OSError:
        pass


def registrar(pasta_app: Path = RAIZ_APP, *, python: str = sys.executable, destino: Path | None = None,
              escrever=_escrever_registro) -> Path:
    from config import EXTENSAO_IDS_PERMITIDOS

    destino = Path(destino or _destino_padrao())
    destino.mkdir(parents=True, exist_ok=True)
    lancador = destino / "transkriptor-ponte.bat"
    host = Path(pasta_app) / "ponte_nativa.py"
    lancador.write_text(f'@echo off\r\n"{python}" "{host}" %*\r\n', encoding="utf-8")
    manifesto = destino / f"{NOME}.json"
    manifesto.write_text(json.dumps({
        "name": NOME,
        "description": "Transkriptor — pareamento local da extensão do Meet",
        "path": str(lancador),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{i}/" for i in EXTENSAO_IDS_PERMITIDOS],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    for chave in CHAVES:
        escrever(chave, str(manifesto))
    return manifesto


def desregistrar(*, destino: Path | None = None, apagar=_apagar_registro) -> None:
    for chave in CHAVES:
        apagar(chave)
    destino = Path(destino or _destino_padrao())
    for nome in (f"{NOME}.json", "transkriptor-ponte.bat"):
        try:
            (destino / nome).unlink()
        except OSError:
            pass


if __name__ == "__main__":
    if "--remover" in sys.argv:
        desregistrar()
        print("Host de pareamento removido.")
    else:
        print(f"Host de pareamento registrado: {registrar()}")
