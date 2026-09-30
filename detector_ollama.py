# -*- coding: utf-8 -*-
"""Onde está o Ollama e o que ele tem (T-15.D1 / interfaces §6).

Ordem: API na URL configurada (loopback); se muda, executável no PATH, na
pasta padrão do instalador e nas chaves de desinstalação do usuário (HKCU).
Executável sem API = "parado" (dá para iniciar); nada = "nao_instalado".
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

from provedores_ia import ModeloIA, ProvedorOllama, normalizar_url_ollama, url_ollama


@dataclass(frozen=True)
class DeteccaoOllama:
    estado: str  # online | parado | nao_instalado
    versao: str | None
    url: str
    executavel: str | None
    modelos: list[ModeloIA] = field(default_factory=list)


def _instalacoes_registro() -> list[str]:
    """InstallLocation das entradas "Ollama" em HKCU\\...\\Uninstall (só leitura)."""
    try:
        import winreg
    except ImportError:
        return []
    caminhos = []
    raiz = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, raiz) as chave:
            for i in range(winreg.QueryInfoKey(chave)[0]):
                try:
                    with winreg.OpenKey(chave, winreg.EnumKey(chave, i)) as sub:
                        nome = str(winreg.QueryValueEx(sub, "DisplayName")[0])
                        if "ollama" in nome.lower():
                            caminhos.append(str(winreg.QueryValueEx(sub, "InstallLocation")[0]))
                except OSError:
                    continue
    except OSError:
        return []
    return caminhos


def _executavel(which, existe, instalacoes_registro) -> str | None:
    achado = which("ollama")
    if achado:
        return achado
    padrao = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    if existe(padrao):
        return padrao
    for pasta in instalacoes_registro():
        candidato = os.path.join(pasta.rstrip("\\/"), "ollama.exe")
        if existe(candidato):
            return candidato
    return None


def detectar_ollama(url_config: str | None = None, *, timeout_s: float = 2.0, which=shutil.which,
                    existe=os.path.isfile, instalacoes_registro=_instalacoes_registro) -> DeteccaoOllama:
    url = normalizar_url_ollama(url_config) if url_config else url_ollama()
    provedor = ProvedorOllama(url)
    try:
        versao = provedor.versao(timeout_s)
    except Exception:  # noqa: BLE001 — API muda: procurar o executável
        executavel = _executavel(which, existe, instalacoes_registro)
        return DeteccaoOllama("parado" if executavel else "nao_instalado", None, url, executavel, [])
    return DeteccaoOllama("online", versao, url, _executavel(which, existe, instalacoes_registro),
                          provedor.listar_modelos(timeout_s))
