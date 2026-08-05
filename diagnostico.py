# -*- coding: utf-8 -*-
"""Autodiagnóstico do Transkriptor (FR-9.5).

Existe por um motivo concreto: o app passou dias "rodando" sem gravar nada e
sem nenhum sinal para o usuário. Duas falhas silenciosas ao mesmo tempo — o
título do Meet tinha mudado de formato e a captura de áudio levantava exceção
engolida por um `except: continue`. Nenhuma das duas aparecia no log.

Este módulo responde, em uma tela, "por que o Transkriptor não está gravando?".
"""

from __future__ import annotations

import logging
import os
import platform
import sys

from config import (
    INTERVALO_MONITOR_MEET,
    LOG_FILE,
    PASTA_TRANSCRICOES,
    VERSAO,
)

logger = logging.getLogger(__name__)

OK = "OK"
AVISO = "AVISO"
ERRO = "ERRO"


def _item(nome, estado, detalhe=""):
    return {"nome": nome, "estado": estado, "detalhe": str(detalhe)}


def checar_dependencias_audio():
    """A incompatibilidade soundcard × numpy 2 quebra a captura silenciosamente."""
    itens = []
    try:
        import numpy

        versao_numpy = str(numpy.__version__)
    except Exception as e:  # noqa: BLE001
        return [_item("numpy", ERRO, f"não instalado: {e}")]
    try:
        import importlib.metadata as md

        versao_sc = md.version("soundcard")
    except Exception as e:  # noqa: BLE001
        return [_item("soundcard", ERRO, f"não instalado: {e}")]

    itens.append(_item("numpy", OK, versao_numpy))
    if _versao_menor(versao_sc, (0, 4, 6)) and _versao_maior_ou_igual(versao_numpy, (2, 0)):
        itens.append(
            _item(
                "soundcard",
                ERRO,
                f"{versao_sc} é incompatível com numpy {versao_numpy} "
                "(numpy.fromstring foi removido). Rode: pip install -U \"soundcard>=0.4.6\"",
            )
        )
    else:
        itens.append(_item("soundcard", OK, versao_sc))
    return itens


def _tupla_versao(texto):
    partes = []
    for pedaco in str(texto).split("."):
        digitos = "".join(c for c in pedaco if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes)


def _versao_menor(texto, alvo):
    return _tupla_versao(texto) < alvo


def _versao_maior_ou_igual(texto, alvo):
    return _tupla_versao(texto) >= alvo


def checar_audio(testar_loopback=None, testar_microfone=None, capturar_mic=True):
    """Grava meio segundo de loopback (e mic) e reporta o resultado real."""
    if testar_loopback is None or testar_microfone is None:
        from audio_utils import testar_loopback as _tl, testar_microfone as _tm

        testar_loopback = testar_loopback or _tl
        testar_microfone = testar_microfone or _tm

    itens = []
    r = testar_loopback()
    if not r.get("ok"):
        itens.append(_item("Áudio do sistema (loopback)", ERRO, r.get("motivo", "")))
    elif r.get("rms", 0.0) <= 0.0:
        itens.append(
            _item(
                "Áudio do sistema (loopback)",
                AVISO,
                f"captura funciona em '{r.get('dispositivo', '')}', mas está em silêncio "
                "agora (normal se nada estiver tocando)",
            )
        )
    else:
        itens.append(
            _item("Áudio do sistema (loopback)", OK, f"{r.get('dispositivo', '')} (com som)")
        )

    if capturar_mic:
        m = testar_microfone()
        if not m.get("ok"):
            itens.append(_item("Microfone", AVISO, m.get("motivo", "")))
        else:
            itens.append(_item("Microfone", OK, m.get("dispositivo", "")))
    return itens


def checar_deteccao(detector):
    """Mostra o que cada fonte está vendo agora."""
    if detector is None:
        return [_item("Detecção", ERRO, "detector não inicializado")]
    itens = []
    algum = False
    for sinal in detector.instantaneo():
        if sinal.ativo:
            algum = True
            estado, prefixo = OK, "detectou"
        else:
            estado, prefixo = AVISO, "sem sinal"
        itens.append(
            _item(f"Fonte: {sinal.fonte}", estado, f"{prefixo} — {sinal.detalhe}")
        )
    itens.append(
        _item(
            "Reunião agora",
            OK if algum else AVISO,
            "detectada" if algum else "nenhuma reunião detectada neste instante",
        )
    )
    return itens


def checar_modelo_whisper(modelo_nome):
    """O modelo do Whisper baixa na primeira reunião; avisar antes evita susto."""
    try:
        from config import detectar_cuda_e_vram, resolver_modelo_whisper

        if modelo_nome == "auto":
            tem_cuda, vram = detectar_cuda_e_vram()
            modelo, device, _ctype = resolver_modelo_whisper(tem_cuda, vram)
            return [
                _item(
                    "Modelo Whisper",
                    OK,
                    f"auto → {modelo} em {device}"
                    + (f" (GPU {vram:.1f} GB)" if tem_cuda else " (sem GPU)"),
                )
            ]
        return [_item("Modelo Whisper", OK, str(modelo_nome))]
    except Exception as e:  # noqa: BLE001
        return [_item("Modelo Whisper", AVISO, f"não foi possível resolver: {e}")]


def checar_ambiente():
    itens = [
        _item("Versão", OK, VERSAO),
        _item("Python", OK, sys.version.split()[0]),
        _item("Windows", OK, platform.platform()),
    ]
    try:
        import shutil

        livre_gb = shutil.disk_usage(PASTA_TRANSCRICOES).free / (1024**3)
        estado = OK if livre_gb >= 2 else AVISO
        itens.append(_item("Espaço em disco", estado, f"{livre_gb:.1f} GB livres"))
    except Exception as e:  # noqa: BLE001
        itens.append(_item("Espaço em disco", AVISO, str(e)))
    itens.append(_item("Intervalo do monitor", OK, f"{INTERVALO_MONITOR_MEET}s"))
    return itens


def coletar(detector=None, modelo_whisper="auto", capturar_mic=True, gravando=False):
    """Roda todas as checagens e devolve a lista de itens."""
    itens = []
    itens.append(
        _item(
            "Gravando agora",
            OK if gravando else AVISO,
            "sim" if gravando else "não (aguardando reunião)",
        )
    )
    itens += checar_ambiente()
    itens += checar_dependencias_audio()
    try:
        itens += checar_audio(capturar_mic=capturar_mic)
    except Exception as e:  # noqa: BLE001
        itens.append(_item("Áudio", ERRO, f"autoteste falhou: {e}"))
    itens += checar_deteccao(detector)
    itens += checar_modelo_whisper(modelo_whisper)
    return itens


def resumir(itens):
    """`(quantos_erros, quantos_avisos)` — usado para o toast final."""
    erros = sum(1 for i in itens if i["estado"] == ERRO)
    avisos = sum(1 for i in itens if i["estado"] == AVISO)
    return erros, avisos


def formatar_texto(itens):
    """Relatório legível para salvar em arquivo e abrir no Bloco de Notas."""
    largura = max((len(i["nome"]) for i in itens), default=10)
    linhas = [
        f"Diagnóstico do Transkriptor {VERSAO}",
        "=" * 60,
        "",
    ]
    for i in itens:
        linhas.append(f"[{i['estado']:5}] {i['nome']:<{largura}}  {i['detalhe']}")
    erros, avisos = resumir(itens)
    linhas += [
        "",
        "=" * 60,
        f"{erros} erro(s), {avisos} aviso(s).",
        "",
        "Como ler este relatório:",
        "  ERRO  — impede a gravação; resolva antes de contar com o app.",
        "  AVISO — pode ser normal (ex.: silêncio quando nada está tocando).",
        "",
        f"Log completo: {LOG_FILE}",
    ]
    return "\n".join(linhas)


def salvar_relatorio(texto, pasta=None):
    """Grava o relatório e devolve o caminho."""
    import datetime

    pasta = pasta or os.path.dirname(LOG_FILE)
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(
        pasta, f"diagnostico_{datetime.datetime.now():%Y-%m-%d_%Hh%M}.txt"
    )
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    return caminho
