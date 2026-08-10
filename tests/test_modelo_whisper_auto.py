# -*- coding: utf-8 -*-
"""Testes de resolução automática do modelo Whisper (FR-6.3, FR-6.4)."""
from unittest.mock import MagicMock, patch

import app_ciclo_reuniao
from config import MODELO_WHISPER, resolver_modelo_whisper


def test_modelo_whisper_default_auto():
    """FR-6.3: default do produto é auto."""
    assert MODELO_WHISPER == "auto"


def test_resolver_cuda_vram_4gb_medium():
    """FR-6.3: GTX 1650 4 GB → medium/cuda/int8_float16."""
    assert resolver_modelo_whisper(True, 4.0) == ("medium", "cuda", "int8_float16")
    assert resolver_modelo_whisper(True, 6.0) == ("medium", "cuda", "int8_float16")


def test_placa_de_4gb_reporta_menos_de_4_e_ainda_usa_gpu():
    """Regressão v1.4: a GTX 1650 reporta 3.99969 GiB — não pode cair para CPU."""
    assert resolver_modelo_whisper(True, 4294639616 / 1024**3) == (
        "medium",
        "cuda",
        "int8_float16",
    )


def test_resolver_sem_cuda_small_cpu():
    """FR-6.3: sem CUDA → small/cpu/int8."""
    assert resolver_modelo_whisper(False, 8.0) == ("small", "cpu", "int8")


def test_resolver_cuda_vram_baixa_small_cpu():
    """FR-6.3: CUDA com VRAM abaixo do limiar → small/cpu/int8."""
    assert resolver_modelo_whisper(True, 3.5) == ("small", "cpu", "int8")
    assert resolver_modelo_whisper(True, 2.0) == ("small", "cpu", "int8")


def test_detectar_vram_gb_mockavel(monkeypatch):
    """FR-6.3: detecção de VRAM encapsulada e mockável."""
    from config import detectar_vram_gb

    props = MagicMock()
    props.total_memory = int(4 * (1024**3))

    class _Cuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def get_device_properties(_idx):
            return props

    fake_torch = MagicMock()
    fake_torch.cuda = _Cuda()
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)
    # reimport path: função importa torch internamente
    assert detectar_vram_gb() == 4.0


def test_carregar_modelo_auto_usa_resolucao(monkeypatch):
    """FR-6.3: Transcritor com modelo='auto' resolve pelo hardware."""
    monkeypatch.setattr(
        "transcricao_core.resolver_modelo_whisper",
        lambda tem_cuda, vram: ("medium", "cuda", "int8_float16"),
    )
    monkeypatch.setattr("transcricao_core.detectar_cuda_e_vram", lambda: (True, 4.0))
    from transcricao_core import Transcritor

    t = Transcritor(modelo="auto", diarizar_ao_final=False)
    mock_model = MagicMock()
    with patch("transcricao_core.WhisperModel", return_value=mock_model) as wm:
        t._carregar_modelo()
        wm.assert_called_once_with("medium", device="cuda", compute_type="int8_float16")
    assert t._modelo is mock_model
    assert t.modelo_nome == "medium" or t.modelo_nome == "auto"


def test_carregar_modelo_auto_fallback_cuda_para_cpu(monkeypatch):
    """FR-6.3: falha ao carregar CUDA → re-tenta small/cpu/int8."""
    monkeypatch.setattr(
        "transcricao_core.resolver_modelo_whisper",
        lambda tem_cuda, vram: ("medium", "cuda", "int8_float16"),
    )
    monkeypatch.setattr("transcricao_core.detectar_cuda_e_vram", lambda: (True, 4.0))
    from transcricao_core import Transcritor

    t = Transcritor(modelo="auto", diarizar_ao_final=False)
    mock_model = MagicMock()
    calls = {"n": 0}

    def _wm(nome, device=None, compute_type=None):
        calls["n"] += 1
        if device == "cuda":
            raise RuntimeError("CUDA OOM simulado")
        return mock_model

    with patch("transcricao_core.WhisperModel", side_effect=_wm) as wm:
        t._carregar_modelo()
        assert calls["n"] == 2
        # última chamada: small/cpu
        args, kwargs = wm.call_args
        assert args[0] == "small"
        assert kwargs.get("device") == "cpu"
        assert kwargs.get("compute_type") == "int8"
    assert t._modelo is mock_model


def test_carregar_modelo_explicito_nao_resolve_auto(monkeypatch):
    """Modelo fixo (base/small/...) não passa por resolução auto."""
    from transcricao_core import Transcritor

    t = Transcritor(modelo="base", diarizar_ao_final=False)
    mock_model = MagicMock()
    with patch("transcricao_core.WhisperModel", return_value=mock_model) as wm:
        with patch("transcricao_core.resolver_device_whisper", return_value="cpu"):
            t._carregar_modelo()
        assert wm.call_args.args[0] == "base" or wm.call_args[0][0] == "base"


def test_menu_persiste_modelo_whisper(tmp_path, monkeypatch, modulo_transkriptor):
    """FR-6.4: escolher modelo no menu persiste via config_user.atualizar."""
    import config_user

    caminho = tmp_path / "config_user.json"
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", str(caminho))
    config_user.salvar({})

    app = modulo_transkriptor.AppTranskriptor.__new__(modulo_transkriptor.AppTranskriptor)
    app.modelo_whisper = "auto"
    app.icone = None
    app._status = MagicMock()
    app._atualizar_tooltip = MagicMock()
    app._lock = __import__("threading").Lock()

    toasts = []

    def _toast(titulo, msg, *a, **k):
        toasts.append(msg)

    monkeypatch.setattr(modulo_transkriptor, "notificar", _toast)
    monkeypatch.setattr("app_bandeja_menu.notificar", _toast)
    monkeypatch.setattr("notificador.notificar", _toast)

    app.definir_modelo_whisper(None, "medium")
    assert app.modelo_whisper == "medium"
    assert config_user.carregar().get("modelo_whisper") == "medium"
    assert any("próxima" in m or "proxima" in m.lower() for m in toasts)


def test_iniciar_transcricao_usa_modelo_da_config(monkeypatch, modulo_transkriptor):
    """FR-6.4: Transcritor recebe o modelo escolhido no app."""
    capturados = {}

    class _FakeTranscritor:
        def __init__(self, **kwargs):
            capturados.update(kwargs)
            self.on_status = kwargs["on_status"]
            self.rodando = False
            self.diarizando = False

        def start(self):
            # O Transcritor real reporta status de dentro do start; o dublê
            # precisa fazer o mesmo ou não exercita o caminho que travou o app.
            self.rodando = True
            self.on_status("Gravação da reunião em andamento.")

    monkeypatch.setitem(
        __import__("sys").modules,
        "transcricao_core",
        MagicMock(Transcritor=_FakeTranscritor),
    )
    # reimport path used inside _iniciar_transcricao is local import
    import types

    fake_mod = types.ModuleType("transcricao_core")
    fake_mod.Transcritor = _FakeTranscritor
    monkeypatch.setitem(__import__("sys").modules, "transcricao_core", fake_mod)

    app = modulo_transkriptor.AppTranskriptor.__new__(modulo_transkriptor.AppTranskriptor)
    app.transcritor = None
    app.watchdog = None
    app.modelo_whisper = "small"
    app.diarizacao_ativa = False
    app.capturar_mic = False
    app.identificar_minha_voz = False
    app.rotulo_usuario = "VOCÊ"
    app.criptografar_transcricoes = False
    app._inicio_transcricao_wall_ms = None
    app._lock = __import__("threading").Lock()
    app._status = MagicMock()
    app._atualizar_tooltip = MagicMock()
    app._erro_critico = MagicMock()
    monkeypatch.setattr(app_ciclo_reuniao, "notificar", lambda *a, **k: None)
    monkeypatch.setattr(app_ciclo_reuniao, "Watchdog", MagicMock())
    monkeypatch.setattr(app_ciclo_reuniao, "perfil_existe", lambda *a, **k: False)

    # _iniciar_transcricao faz `from transcricao_core import Transcritor`
    app._iniciar_transcricao()
    assert capturados.get("modelo") == "small"
