# -*- coding: utf-8 -*-
"""Fixtures compartilhadas do pytest."""
import hashlib
import os
import socket
import sys
import threading
import wave
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import pytest


REPO_TESTES = Path(__file__).resolve().parent.parent


@dataclass
class RelogioControlado:
    """Relógio monotônico explícito para testes sem `sleep` real."""

    agora_ns: int = 0

    def monotonic_ns(self) -> int:
        return self.agora_ns

    def avancar_ms(self, milissegundos: int) -> None:
        if milissegundos < 0:
            raise ValueError("o relógio controlado não retrocede")
        self.agora_ns += milissegundos * 1_000_000


class ServidorTemporario:
    """Servidor TCP local de teste com thread e socket encerráveis."""

    def __init__(self, resposta: bytes) -> None:
        self.host = "127.0.0.1"
        self.resposta = resposta
        self._encerrado = threading.Event()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, 0))
        self._socket.listen()
        self._socket.settimeout(0.1)
        self.porta = self._socket.getsockname()[1]
        self.thread = threading.Thread(target=self._atender, daemon=True)
        self.thread.start()

    def _atender(self) -> None:
        while not self._encerrado.is_set():
            try:
                conexao, _ = self._socket.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conexao:
                try:
                    conexao.recv(4096)
                    if self.resposta:
                        conexao.sendall(self.resposta)
                except OSError:
                    continue

    def fechar(self) -> None:
        if self._encerrado.is_set():
            return
        self._encerrado.set()
        self._socket.close()
        self.thread.join(timeout=2)


@pytest.fixture
def relogio_controlado():
    return RelogioControlado()


@pytest.fixture
def wav_sintetico(tmp_path):
    """Cria WAV PCM 16-bit determinístico, sem dispositivo de áudio."""

    def criar(
        fonte: str,
        *,
        frames: int = 1_600,
        sample_rate: int = 16_000,
        channels: int = 1,
    ) -> Path:
        if frames < 0 or sample_rate <= 0 or channels <= 0:
            raise ValueError("parâmetros WAV sintético inválidos")
        caminho = tmp_path / f"{fonte}.wav"
        amostras = b"\xe8\x03\x18\xfc" * ((frames * channels + 1) // 2)
        with wave.open(str(caminho), "wb") as arquivo:
            arquivo.setnchannels(channels)
            arquivo.setsampwidth(2)
            arquivo.setframerate(sample_rate)
            arquivo.writeframes(amostras[: frames * channels * 2])
        return caminho

    return criar


@pytest.fixture
def servidor_temporario():
    """Entrega servidores 127.0.0.1 e garante encerramento no teardown."""
    servidores: list[ServidorTemporario] = []

    def iniciar(*, resposta: bytes = b"") -> ServidorTemporario:
        servidor = ServidorTemporario(resposta)
        servidores.append(servidor)
        return servidor

    yield iniciar

    for servidor in reversed(servidores):
        servidor.fechar()


def _raiz_estado_real() -> Path:
    """Retorna o checkout principal mesmo quando a suíte roda em worktree."""
    override = os.environ.get("TRANSKRIPTOR_ESTADO_REAL_ROOT")
    if override:
        return Path(override).resolve()
    marcador_git = REPO_TESTES / ".git"
    if marcador_git.is_file():
        primeira = marcador_git.read_text(encoding="utf-8").strip()
        if primeira.lower().startswith("gitdir:"):
            gitdir = Path(primeira.split(":", 1)[1].strip())
            if not gitdir.is_absolute():
                gitdir = (REPO_TESTES / gitdir).resolve()
            if gitdir.parent.name == "worktrees":
                return gitdir.parent.parent.parent.resolve()
    return REPO_TESTES


def _hash_arquivo(caminho: Path) -> str | None:
    if not caminho.is_file():
        return None
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(64 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _metadados_arvore(pasta: Path) -> tuple:
    """Compara nomes/tamanho/mtime; nunca abre conteúdo de transcrição."""
    if not pasta.is_dir():
        return ()
    itens = []
    for raiz, diretorios, arquivos in os.walk(pasta, followlinks=False):
        diretorios.sort()
        arquivos.sort()
        raiz_path = Path(raiz)
        for nome in diretorios:
            caminho = raiz_path / nome
            stat = caminho.stat()
            itens.append(("d", caminho.relative_to(pasta).as_posix(), stat.st_mtime_ns))
        for nome in arquivos:
            caminho = raiz_path / nome
            stat = caminho.stat()
            itens.append(
                ("f", caminho.relative_to(pasta).as_posix(), stat.st_size, stat.st_mtime_ns)
            )
    return tuple(itens)


def _snapshot_estado_real() -> dict:
    raiz = _raiz_estado_real()
    appdata = Path(os.environ.get("APPDATA", ""))
    perfil = Path(os.environ.get("USERPROFILE", ""))
    atalhos = (
        appdata
        / "Microsoft/Windows/Start Menu/Programs/Startup/transkriptor.lnk",
        perfil / "Desktop/Transkriptor.lnk",
        perfil / "OneDrive/Desktop/Transkriptor.lnk",
    )
    return {
        "config_sha256": _hash_arquivo(raiz / "config_user.json"),
        "chave_sha256": _hash_arquivo(
            raiz / "_modelo_voz" / "transkriptor_key.dpapi"
        ),
        "transcricoes_metadados": _metadados_arvore(raiz / "transcricoes"),
        "atalhos_sha256": tuple((str(p), _hash_arquivo(p)) for p in atalhos),
    }


@pytest.fixture(scope="session", autouse=True)
def log_de_teste(tmp_path_factory):
    """A suíte não pode escrever no `transkriptor.log` do usuário.

    Ao carregar `transkriptor.pyw` os testes instalam um RotatingFileHandler na
    raiz do logging. Sem isto ele aponta para o log de produção e a suíte enche
    o arquivo com falhas simuladas ("CUDA OOM simulado", "falha controlada") —
    foi o que contaminou a evidência do incidente de 2026-08-07.
    """
    import config

    destino = tmp_path_factory.mktemp("log") / "transkriptor-teste.log"
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "LOG_FILE", str(destino))
    for modulo in tuple(sys.modules.values()):
        if modulo is not None and hasattr(modulo, "LOG_FILE"):
            mp.setattr(modulo, "LOG_FILE", str(destino), raising=False)
    yield destino
    mp.undo()


@pytest.fixture
def snapshot_estado_real():
    return _snapshot_estado_real


@pytest.fixture(autouse=True)
def _guardar_estado_real(snapshot_estado_real):
    """Falha imediatamente se qualquer teste tocar os artefatos do usuário."""
    antes = snapshot_estado_real()
    yield
    assert snapshot_estado_real() == antes, "teste alterou estado local real do usuário"


@pytest.fixture(autouse=True)
def _isolar_estado_local(monkeypatch, tmp_path):
    """Redireciona toda persistência local conhecida para uma pasta temporária.

    O guard acima continua obrigatório: ele cobre caminhos futuros que alguém
    esqueça de redirecionar aqui.
    """
    estado = tmp_path / "estado_local"
    transcricoes = estado / "transcricoes"
    audio = transcricoes / "audio"
    modelo_voz = estado / "_modelo_voz"
    startup = estado / "Startup" / "transkriptor.lnk"
    audio.mkdir(parents=True, exist_ok=True)
    modelo_voz.mkdir(parents=True, exist_ok=True)

    import config
    import config_user

    substituicoes = {
        "CONFIG_USER_FILE": str(estado / "config_user.json"),
        "ARQUIVO_CHAVE_DPAPI": str(modelo_voz / "transkriptor_key.dpapi"),
        "PASTA_TRANSCRICOES": str(transcricoes),
        "PASTA_AUDIO": str(audio),
    }
    for nome, valor in substituicoes.items():
        if hasattr(config, nome):
            monkeypatch.setattr(config, nome, valor)
    monkeypatch.setattr(config_user, "CONFIG_USER_FILE", substituicoes["CONFIG_USER_FILE"])

    # Módulos importados na coleta já copiaram constantes de config.
    for modulo in tuple(sys.modules.values()):
        if modulo is None:
            continue
        nome_modulo = getattr(modulo, "__name__", "")
        if not nome_modulo.startswith(
            (
                "assistente",
                "app_bandeja_menu",
                "app_ciclo_reuniao",
                "crypto_storage",
                "diagnostico",
                "retranscritor",
                "transcricao_core",
                "transkriptor_",
            )
        ):
            continue
        for nome, valor in substituicoes.items():
            if hasattr(modulo, nome):
                monkeypatch.setattr(modulo, nome, valor)

    try:
        import startup_windows

        monkeypatch.setattr(startup_windows, "ATALHO_STARTUP", str(startup))
    except ImportError:
        pass
    return estado


@pytest.fixture
def headers_token():
    from assistente import HEADER_TOKEN, obter_token_sessao

    return {HEADER_TOKEN: obter_token_sessao()}


@pytest.fixture
def chave_teste(monkeypatch, tmp_path):
    cfg = tmp_path / "config_user.json"
    chave_dpapi = tmp_path / "transkriptor_key.dpapi"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("config_user.CONFIG_USER_FILE", str(cfg))
    monkeypatch.setattr("config.ARQUIVO_CHAVE_DPAPI", str(chave_dpapi))
    monkeypatch.setattr("crypto_storage._dpapi_protect", lambda b: b"DPAPI:" + b)
    monkeypatch.setattr("crypto_storage._dpapi_unprotect", lambda b: b[6:])
    from crypto_storage import garantir_chave_mestra

    garantir_chave_mestra()
    return cfg


@pytest.fixture
def tmp_transcricoes(tmp_path):
    """Pasta isolada com um arquivo de transcrição de exemplo."""
    pasta = tmp_path / "transcricoes"
    pasta.mkdir()
    arquivo = pasta / "transcricao_2026-07-08_10h00.txt"
    arquivo.write_text(
        "=== Transcricao iniciada em 2026-07-08 10:00:00 ===\n\n"
        "[10:00:01] Ola equipe\n",
        encoding="utf-8",
    )
    return pasta


@pytest.fixture(scope="session")
def modulo_transkriptor(log_de_teste):
    """Carrega o app .pyw sem executar o bloco __main__.

    Depende de `log_de_teste` de propósito: o handler de log é instalado no
    momento em que este módulo é executado, e precisa apontar para o temporário.
    """
    caminho = Path(__file__).resolve().parent.parent / "transkriptor.pyw"
    loader = SourceFileLoader("transkriptor_app_test", str(caminho))
    spec = spec_from_loader(loader.name, loader)
    modulo = module_from_spec(spec)
    loader.exec_module(modulo)
    return modulo
