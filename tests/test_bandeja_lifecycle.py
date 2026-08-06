# -*- coding: utf-8 -*-
"""Regressões do ciclo de vida Win32 da bandeja (v1.2.1)."""
from pathlib import Path
import subprocess
import sys
import threading


REPO = Path(__file__).resolve().parent.parent


class IconeFalso:
    instancia = None

    def __init__(self, *args, **kwargs):
        type(self).instancia = self
        self.ready = False
        self.visible_events = []
        self.notifications = []
        self._visible = False
        self.stopped = False

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, valor):
        self.visible_events.append((valor, self.ready))
        self._visible = valor

    def run(self, setup=None):
        self.ready = True
        if setup is not None:
            setup(self)

    def notify(self, mensagem, titulo):
        self.notifications.append((mensagem, titulo, self.ready))

    def stop(self):
        self.stopped = True


class ThreadFalsa:
    eventos = []

    def __init__(self, target, daemon=False, name=None):
        self.target = target
        self.daemon = daemon
        self.name = name
        self._alive = False

    def start(self):
        self._alive = True
        ThreadFalsa.eventos.append(IconeFalso.instancia.ready)

    def is_alive(self):
        return self._alive


def _app_minimo(modulo):
    app = modulo.AppTranskriptor.__new__(modulo.AppTranskriptor)
    app.iniciar_com_windows = False
    app.usar_nomes_meet = False
    app._meet_bridge_thread = None
    app._monitor_thread = None
    app._bandeja_pronta = False
    app._lock = threading.Lock()
    app._menu = lambda: None
    app._monitorar_meet = lambda: None
    return app


def _preparar_rodar(monkeypatch, modulo_transkriptor):
    ThreadFalsa.eventos.clear()
    monkeypatch.setattr(modulo_transkriptor.pystray, "Icon", IconeFalso)
    monkeypatch.setattr(modulo_transkriptor.threading, "Thread", ThreadFalsa)
    monkeypatch.setattr(modulo_transkriptor, "criar_ico", lambda: None)
    monkeypatch.setattr(modulo_transkriptor, "criar_imagem", lambda: object())
    monkeypatch.setattr(modulo_transkriptor, "_startup_ativo", lambda: False)
    monkeypatch.setattr(modulo_transkriptor, "notificar", lambda *args, **kwargs: None)


def test_icone_so_fica_visivel_depois_do_backend_pronto(monkeypatch, modulo_transkriptor):
    _preparar_rodar(monkeypatch, modulo_transkriptor)

    app = _app_minimo(modulo_transkriptor)
    app.rodar()

    assert IconeFalso.instancia.visible_events == [(True, True)]


def test_registra_icone_unico_sem_balao_duplicado_de_startup(
    monkeypatch, modulo_transkriptor
):
    _preparar_rodar(monkeypatch, modulo_transkriptor)
    registrados = []
    monkeypatch.setattr(modulo_transkriptor, "configurar_icone", registrados.append)

    app = _app_minimo(modulo_transkriptor)
    app.rodar()

    assert registrados == [IconeFalso.instancia]
    assert IconeFalso.instancia.notifications == []


def test_monitor_so_inicia_depois_da_bandeja_pronta(monkeypatch, modulo_transkriptor):
    _preparar_rodar(monkeypatch, modulo_transkriptor)

    app = _app_minimo(modulo_transkriptor)
    app.rodar()

    # retencao + monitor
    assert ThreadFalsa.eventos
    assert all(ThreadFalsa.eventos)
    assert len(ThreadFalsa.eventos) >= 1


def test_setup_repetido_nao_duplica_monitor(monkeypatch, modulo_transkriptor):
    ThreadFalsa.eventos.clear()
    monkeypatch.setattr(modulo_transkriptor.threading, "Thread", ThreadFalsa)
    monkeypatch.setattr(modulo_transkriptor, "notificar", lambda *args, **kwargs: None)
    app = _app_minimo(modulo_transkriptor)
    icon = IconeFalso()
    icon.ready = True

    app._ao_bandeja_pronta(icon)
    n_primeira = len(ThreadFalsa.eventos)
    app._ao_bandeja_pronta(icon)

    assert n_primeira >= 1
    assert len(ThreadFalsa.eventos) == n_primeira


def test_falha_no_setup_para_icone_e_mostra_erro(monkeypatch, modulo_transkriptor):
    class ThreadComFalha(ThreadFalsa):
        def start(self):
            raise RuntimeError("falha controlada")

    erros = []
    monkeypatch.setattr(modulo_transkriptor.threading, "Thread", ThreadComFalha)
    monkeypatch.setattr(modulo_transkriptor, "notificar", lambda *args, **kwargs: None)
    monkeypatch.setattr(modulo_transkriptor, "_mostrar_erro_fatal", erros.append)
    app = _app_minimo(modulo_transkriptor)
    icon = IconeFalso()
    icon.ready = True

    app._ao_bandeja_pronta(icon)

    assert icon.stopped is True
    assert erros == ["Não foi possível preparar a bandeja do Transkriptor."]


def test_startup_da_bandeja_nao_importa_whisper_antes_do_meet():
    codigo = r"""
from importlib.machinery import SourceFileLoader
import sys

SourceFileLoader("transkriptor_startup_test", "transkriptor.pyw").load_module()
print("transcricao_core" in sys.modules)
"""

    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )

    assert resultado.stdout.strip() == "False"
