# -*- coding: utf-8 -*-
"""T-15.D1 / interfaces §6 — onde está o Ollama e o que ele tem."""
from __future__ import annotations

import pytest

from detector_ollama import detectar_ollama
from tests.fake_ollama import FakeOllama


def _sem_nada(**kw):
    base = dict(which=lambda _n: None, existe=lambda _p: False, instalacoes_registro=lambda: [])
    base.update(kw)
    return base


def test_online_lista_modelos():
    f = FakeOllama(modelos=["granite4.1:3b"])
    f.start()
    try:
        d = detectar_ollama(f.url, **_sem_nada())
    finally:
        f.stop()
    assert d.estado == "online" and d.versao == "0.34.4-fake"
    assert [m.id for m in d.modelos] == ["granite4.1:3b"]


def test_ordem_de_busca_do_executavel():
    url = "http://127.0.0.1:1"
    assert detectar_ollama(url, **_sem_nada(which=lambda n: r"C:\bin\ollama.exe")).executavel == r"C:\bin\ollama.exe"
    padrao = detectar_ollama(url, **_sem_nada(existe=lambda p: p.endswith(r"Programs\Ollama\ollama.exe")))
    assert padrao.executavel.endswith(r"Programs\Ollama\ollama.exe")
    reg = detectar_ollama(url, **_sem_nada(instalacoes_registro=lambda: [r"D:\Apps\Ollama"],
                                             existe=lambda p: p == r"D:\Apps\Ollama\ollama.exe"))
    assert reg.executavel == r"D:\Apps\Ollama\ollama.exe"


def test_parado_quando_exe_sem_api():
    d = detectar_ollama("http://127.0.0.1:1", **_sem_nada(which=lambda n: r"C:\bin\ollama.exe"))
    assert d.estado == "parado" and d.modelos == []


def test_nao_instalado():
    d = detectar_ollama("http://127.0.0.1:1", **_sem_nada())
    assert d.estado == "nao_instalado" and d.executavel is None


def test_url_fora_do_loopback_nao_e_consultada():
    with pytest.raises(ValueError):
        detectar_ollama("http://192.168.0.2:11434", **_sem_nada())
