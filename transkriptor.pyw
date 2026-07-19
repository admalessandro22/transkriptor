# -*- coding: utf-8 -*-
"""
Transkriptor - app de bandeja que detecta Google Meets e transcreve em segundo plano.

- Fica na bandeja do sistema ao ser aberto.
- Detecta automaticamente o inicio de um Google Meet (titulo da janela do navegador).
- Inicia a transcricao em segundo plano e salva em .txt na pasta 'transcricoes'.
- Menu da bandeja: abrir pasta de transcricoes, pausar/retomar deteccao, sair.
"""

import json
import logging
import secrets
from logging.handlers import RotatingFileHandler
import os
import subprocess
import sys
import threading
import time

from PIL import Image, ImageDraw
import pygetwindow as gw
import pystray

from detector_meet import DetectorMeet, titulo_eh_meet
from watchdog import Watchdog
from notificador import (
    deve_toast_ao_vivo,
    formatar_mensagem_toast,
    meet_em_foco,
    notificar,
)
from transkriptor_acoes import (
    confirmacao_saida_necessaria,
    deve_parar_transcricao_por_meet,
    saida_permitida,
    texto_transcricao_manual,
)
from estado_icone import DURACAO_ERRO_ICONE, cor_por_estado, resolver_estado_icone
from transkriptor_lock import adquirir_lock, liberar_lock
from config import (
    BASE_DIR,
    PASTA_TRANSCRICOES,
    LOG_FILE,
    ICONE_FILE,
    MODELO_WHISPER,
    IDIOMA,
    INTERVALO_MONITOR_MEET,
    EXIGIR_JANELA_VISIVEL,
    ARQUIVO_PERFIL_VOZ,
    ARQUIVO_PERFIL_VOZ_ENC,
    ARQUIVO_VOZES_CONHECIDAS,
    ARQUIVO_VOZES_CONHECIDAS_ENC,
    DURACAO_CADASTRO_SEG,
    ROTULO_USUARIO,
    CAPTURAR_MIC,
    PORTA_MEET_BRIDGE,
    USAR_NOMES_MEET,
    MODO_LEGENDAS_MEET,
    VERSAO,
)
from meet_bridge import MeetBridge, iniciar_bridge_em_thread, sincronizar_token_extensao
from status_seguro import sanitizar_para_log
from crypto_storage import (
    chave_disponivel,
    migrar_txt_legacy,
    migrar_vozes_legacy,
    perfil_existe,
)

os.makedirs(PASTA_TRANSCRICOES, exist_ok=True)

LOCK_FILE = os.path.join(BASE_DIR, "transkriptor.lock")

_log_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.root.setLevel(logging.INFO)
logging.root.addHandler(_log_handler)

# Caminhos para startup do Windows (BUG-10)
CONFIG_USER = os.path.join(BASE_DIR, "config_user.json")
STARTUP_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
)
ATALHO_STARTUP = os.path.join(STARTUP_DIR, "transkriptor.lnk")


def _carregar_config_user():
    """Lê config_user.json. Retorna dict vazio se não existir."""
    try:
        with open(CONFIG_USER, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _salvar_config_user(cfg):
    """Salva config_user.json."""
    try:
        with open(CONFIG_USER, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar config_user: {e}")


def _resolver_identificar_minha_voz(cfg, tem_perfil):
    """Ativa identificação só com perfil cadastrado; corrige config inconsistente."""
    ativo = cfg.get("identificar_minha_voz", tem_perfil) and tem_perfil
    if cfg.get("identificar_minha_voz") and not tem_perfil:
        cfg["identificar_minha_voz"] = False
    return ativo, cfg


def _startup_ativo():
    """Retorna True se o atalho de startup existe."""
    return os.path.isfile(ATALHO_STARTUP)


def _criar_atalho_startup():
    """Cria atalho no shell:startup para iniciar com o Windows."""
    try:
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        # Cria via PowerShell
        script = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$lnk = $ws.CreateShortcut("{ATALHO_STARTUP}"); '
            f'$lnk.TargetPath = "{pythonw}"; '
            f'$lnk.Arguments = \'"{os.path.join(BASE_DIR, "transkriptor.pyw")}"\'; '
            f'$lnk.WorkingDirectory = "{BASE_DIR}"; '
            f'$lnk.IconLocation = "{ICONE_FILE}"; '
            f'$lnk.Description = "Transkriptor - Transcricao automatica"; '
            f'$lnk.WindowStyle = 7; '
            f'$lnk.Save()'
        )
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, timeout=10,
        )
        logging.info("Atalho de startup criado.")
        return True
    except Exception as e:
        logging.error(f"Erro ao criar atalho de startup: {e}")
        return False


def _remover_atalho_startup():
    """Remove o atalho de startup."""
    try:
        if os.path.isfile(ATALHO_STARTUP):
            os.remove(ATALHO_STARTUP)
            logging.info("Atalho de startup removido.")
        return True
    except Exception as e:
        logging.error(f"Erro ao remover atalho de startup: {e}")
        return False


def criar_imagem(cor_fundo=None, cor_mic=(255, 255, 255)):
    if cor_fundo is None:
        from estado_icone import COR_AGUARDANDO
        cor_fundo = COR_AGUARDANDO
    """Desenha um microfone simples para o icone da bandeja."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill=cor_fundo)
    # corpo do microfone
    d.rounded_rectangle([24, 14, 40, 38], radius=8, fill=cor_mic)
    # suporte/arco
    d.arc([16, 24, 48, 50], start=20, end=160, fill=cor_mic, width=4)
    # haste
    d.rectangle([30, 46, 34, 54], fill=cor_mic)
    d.rectangle([24, 52, 40, 56], fill=cor_mic)
    return img


# Cache de imagens por estado
_IMAGENS = {}


def imagem_por_estado(estado):
    """Retorna a imagem do ícone para o estado dado (com cache)."""
    if estado not in _IMAGENS:
        _IMAGENS[estado] = criar_imagem(cor_fundo=cor_por_estado(estado))
    return _IMAGENS[estado]


def criar_ico():
    criar_imagem().save(ICONE_FILE, format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])
    return ICONE_FILE


class AppTranskriptor:
    def __init__(self):
        self.icone = None
        self.transcritor = None
        self.watchdog = None
        self.detector = DetectorMeet(exigir_janela_visivel=EXIGIR_JANELA_VISIVEL)
        self.deteccao_ativa = True
        self.diarizacao_ativa = True
        # BUG-10: carrega preferência de startup do Windows
        cfg = _carregar_config_user()
        self.iniciar_com_windows = cfg.get("iniciar_com_windows", _startup_ativo())
        self.criptografar_transcricoes = cfg.get("criptografar_transcricoes", True)
        if self.criptografar_transcricoes and chave_disponivel():
            migrados = migrar_txt_legacy(PASTA_TRANSCRICOES)
            if migrados:
                logging.info("Migradas %d transcricoes .txt para .tkpt", migrados)
            vozes = migrar_vozes_legacy(
                ARQUIVO_PERFIL_VOZ,
                ARQUIVO_PERFIL_VOZ_ENC,
                ARQUIVO_VOZES_CONHECIDAS,
                ARQUIVO_VOZES_CONHECIDAS_ENC,
            )
            if vozes:
                logging.info("Migrados %d arquivos de voz legados para .enc", vozes)
        if "criptografar_transcricoes" not in cfg:
            cfg["criptografar_transcricoes"] = self.criptografar_transcricoes
            _salvar_config_user(cfg)
        tem_perfil = perfil_existe(ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC)
        antes = cfg.get("identificar_minha_voz")
        self.identificar_minha_voz, cfg = _resolver_identificar_minha_voz(cfg, tem_perfil)
        if antes and not tem_perfil:
            _salvar_config_user(cfg)
        self.rotulo_usuario = cfg.get("rotulo_usuario", ROTULO_USUARIO)
        self.capturar_mic = cfg.get("capturar_mic", CAPTURAR_MIC)
        self.usar_nomes_meet = cfg.get("usar_nomes_meet", USAR_NOMES_MEET)
        self.modo_legendas_meet = cfg.get("modo_legendas_meet", MODO_LEGENDAS_MEET)
        cfg_meet = _carregar_config_user()
        meet_token = cfg_meet.get("meet_bridge_token")
        if not meet_token:
            meet_token = secrets.token_urlsafe(24)
            cfg_meet["meet_bridge_token"] = meet_token
            _salvar_config_user(cfg_meet)
        self.meet_bridge = MeetBridge(token=meet_token)
        sincronizar_token_extensao(meet_token, BASE_DIR)
        self._meet_bridge_thread = None
        self._monitor_thread = None
        self._bandeja_pronta = False
        self._inicio_transcricao_wall_ms = None
        self.ultimo_status = "Aguardando Google Meet..."
        self.ultimo_log = ""
        self._lock = threading.Lock()
        self._em_erro = False
        self._instante_erro = None
        self._modo_manual = False

    def _gravando(self):
        return bool(self.transcritor and self.transcritor.rodando)

    def _meet_em_foco(self):
        try:
            ativa = gw.getActiveWindow()
            titulo = ativa.title if ativa else ""
            return meet_em_foco(titulo, titulo_eh_meet)
        except Exception:
            return False

    def _status(self, msg):
        with self._lock:
            self.ultimo_log = msg
        logging.info(sanitizar_para_log(msg))
        if deve_toast_ao_vivo(msg, self._meet_em_foco(), self._gravando()):
            notificar("Transkriptor", formatar_mensagem_toast(msg))
        # UX-02: notifica quando a diarização termina
        if msg.startswith("Diarização concluída"):
            notificar("Transkriptor", f"Vozes separadas: {msg.split(':')[-1].strip()}")
        self._atualizar_tooltip()

    def _atualizar_tooltip(self):
        if self.icone is None:
            return
        estado_icone, estado = resolver_estado_icone(
            self.transcritor,
            self.deteccao_ativa,
            em_erro=self._em_erro,
            instante_erro=self._instante_erro,
        )
        if self._em_erro and estado_icone != "erro":
            self._em_erro = False
            self._instante_erro = None
        self.icone.title = f"Transkriptor {VERSAO} - {estado}"
        # UX-01: troca o ícone conforme o estado
        try:
            self.icone.icon = imagem_por_estado(estado_icone)
        except Exception:
            pass
        self.icone.update_menu()

    def _eventos_meet_relativos(self):
        if self._inicio_transcricao_wall_ms is None:
            return []
        inicio = self._inicio_transcricao_wall_ms
        eventos = self.meet_bridge.drenar_eventos()
        relativos = []
        for ev in eventos:
            ts_ms = ev.get("ts_ms", int(ev.get("ts_sec", 0) * 1000))
            relativos.append({**ev, "ts_sec": (ts_ms - inicio) / 1000.0})
        return relativos

    def _iniciar_transcricao(self, manual=False):
        # O Whisper é pesado e só é necessário quando uma reunião começa.
        # Mantê-lo fora do startup permite registrar a bandeja imediatamente.
        from transcricao_core import Transcritor

        with self._lock:
            if self.transcritor and self.transcritor.rodando:
                return
        self._inicio_transcricao_wall_ms = int(time.time() * 1000)
        if manual:
            self._modo_manual = True
            self._status("Iniciando transcricao manual...")
        else:
            self._status("Meet confirmado. Iniciando transcricao...")
        self.transcritor = Transcritor(
            modelo=MODELO_WHISPER,
            idioma=IDIOMA,
            pasta_saida=PASTA_TRANSCRICOES,
            diarizar_ao_final=self.diarizacao_ativa,
            on_status=self._status,
            capturar_mic=self.capturar_mic,
            identificar_voz=self.identificar_minha_voz and perfil_existe(
                ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC
            ),
            rotulo_usuario=self.rotulo_usuario,
            criptografar=self.criptografar_transcricoes,
        )
        try:
            self.transcritor.start()
            # Inicia watchdog para esta transcrição
            self.watchdog = Watchdog(
                self.transcritor,
                on_status=self._status,
                on_erro_critico=self._erro_critico,
            )
            self.watchdog.start()
            self._status("Transcricao em andamento.")
            notificar("Transkriptor", "Transcrição iniciada (reunião detectada)")
            self._atualizar_tooltip()
        except Exception as e:
            self._status(f"Erro ao iniciar: {e}")
            notificar("Transkriptor", f"Erro ao iniciar transcrição: {e}")

    def _erro_critico(self, msg):
        self._em_erro = True
        self._instante_erro = time.monotonic()
        logging.error(f"Erro critico: {msg}")
        self._status(f"ERRO CRITICO: {msg}")
        notificar("Transkriptor", f"Erro crítico: {msg}. Veja o log.")
        self._atualizar_tooltip()

        def _reverter_erro():
            time.sleep(DURACAO_ERRO_ICONE)
            self._em_erro = False
            self._instante_erro = None
            self._atualizar_tooltip()

        threading.Thread(target=_reverter_erro, daemon=True).start()

    def _parar_transcricao(self):
        with self._lock:
            t = self.transcritor
            w = self.watchdog
        if w:
            w.stop()
            self.watchdog = None
        if t and t.rodando:
            if self.usar_nomes_meet:
                t.eventos_meet = self._eventos_meet_relativos()
                if self.modo_legendas_meet and not t.eventos_meet:
                    notificar(
                        "Transkriptor",
                        "Ative legendas no Meet para identificar participantes",
                    )
            caminho = t.stop()
            if caminho:
                self._status(f"Salvo: {os.path.basename(caminho)}")
                notificar("Transkriptor", f"Transcrição salva: {os.path.basename(caminho)}")
            self._atualizar_tooltip()

    def _processar_mudanca_meet(self, mudanca):
        """Aplica uma mudança confirmada pelo detector à transcrição atual."""
        if mudanca == "iniciou":
            if not self._modo_manual:
                self._iniciar_transcricao()
            return
        if deve_parar_transcricao_por_meet(mudanca, self._modo_manual):
            self._status("Meet encerrado. Finalizando transcricao...")
            self._parar_transcricao()

    def _monitorar_meet(self):
        while True:
            try:
                if self.deteccao_ativa:
                    if EXIGIR_JANELA_VISIVEL:
                        janelas = []
                        for w in gw.getAllWindows():
                            try:
                                janelas.append({
                                    "titulo": w.title,
                                    "visivel": not w.isMinimized,
                                })
                            except Exception:
                                continue
                        mudanca = self.detector.verificar_janelas(janelas)
                    else:
                        mudanca = self.detector.verificar(gw.getAllTitles())
                    self._processar_mudanca_meet(mudanca)
            except Exception:
                logging.exception("Erro no monitor do Meet")
            time.sleep(INTERVALO_MONITOR_MEET)

    # ---- acoes do menu ----
    def abrir_pasta(self, _icone=None, _item=None):
        try:
            os.startfile(PASTA_TRANSCRICOES)
        except Exception as e:
            self._status(f"Erro ao abrir pasta: {e}")

    def abrir_log(self, _icone=None, _item=None):
        try:
            os.startfile(LOG_FILE)
        except Exception as e:
            self._status(f"Erro ao abrir log: {e}")

    def alternar_transcricao_manual(self, _icone=None, _item=None):
        if self._gravando() and self._modo_manual:
            self._parar_transcricao()
            self._modo_manual = False
            self._status("Transcricao manual encerrada.")
            return
        if self._gravando():
            self._status("Ja transcrevendo (Meet ou manual).")
            return
        self._iniciar_transcricao(manual=True)

    def _confirmar_saida(self):
        try:
            import ctypes
            resposta = ctypes.windll.user32.MessageBoxW(
                0,
                "Transcricao em andamento. Parar e sair?",
                "Transkriptor",
                0x00000004 | 0x00000030,
            )
            return resposta == 6
        except Exception:
            return False

    def abrir_assistente(self, _icone=None, _item=None):
        threading.Thread(target=self._iniciar_assistente, daemon=True).start()

    def _abrir_assistente_navegador(self, url, token):
        import webbrowser
        webbrowser.open(f"{url}?token={token}")

    def _iniciar_assistente(self):
        """Inicia o servidor Flask do assistente em segundo plano e abre o navegador."""
        if getattr(self, "_assistente_rodando", False):
            url = getattr(self, "_assistente_url", None)
            token = getattr(self, "_assistente_token", None)
            if url and token:
                self._abrir_assistente_navegador(url, token)
                self._status(f"Assistente já aberto — reabrindo navegador em {url}")
            else:
                self._status("Assistente já está aberto.")
            return
        self._assistente_rodando = True
        self._status("Abrindo assistente de reunião...")
        try:
            import importlib
            assistente = importlib.import_module("assistente")
            porta = assistente.porta_livre()
            url = f"http://127.0.0.1:{porta}"
            import logging as _lg
            _lg.getLogger("werkzeug").setLevel(_lg.WARNING)
            thread = assistente.iniciar_servidor_em_thread(assistente.app, "127.0.0.1", porta)
            if not assistente.aguardar_servidor(url, timeout=10):
                self._status("Erro: assistente não respondeu. Verifique o log.")
                self._assistente_rodando = False
                return
            token = assistente.obter_token_sessao()
            self._assistente_url = url
            self._assistente_token = token
            self._abrir_assistente_navegador(url, token)
            self._status(f"Assistente rodando em {url}")
            thread.join()
        except RuntimeError as e:
            self._status(f"Erro ao abrir assistente: {e}")
            logging.error(f"Erro porta_livre: {e}")
        except Exception as e:
            self._status(f"Erro no assistente: {e}")
            logging.exception("Erro no assistente")
        finally:
            self._assistente_rodando = False
            self._assistente_url = None
            self._assistente_token = None

    def alternar_deteccao(self, _icone=None, _item=None):
        self.deteccao_ativa = not self.deteccao_ativa
        if not self.deteccao_ativa:
            self._parar_transcricao()
            self._status("Deteccao automatica pausada.")
        else:
            self._status("Deteccao automatica retomada.")
        self._atualizar_tooltip()

    def alternar_diarizacao(self, _icone=None, _item=None):
        self.diarizacao_ativa = not self.diarizacao_ativa
        estado = "ativa" if self.diarizacao_ativa else "desativada"
        self._status(f"Separação de vozes {estado}.")
        self._atualizar_tooltip()

    def cadastrar_minha_voz(self, _icone=None, _item=None):
        threading.Thread(target=self._cadastrar_voz_thread, daemon=True).start()

    def _cadastrar_voz_thread(self):
        from identificador_voz import (
            gravar_audio_microfone,
            perfil_de_chunks,
            salvar_perfil,
        )
        from diarizador import _carregar_encoder

        notificar(
            "Transkriptor",
            f"Fale por {DURACAO_CADASTRO_SEG}s após o sinal. Leia um texto em voz alta.",
        )
        self._status(f"Gravando perfil de voz ({DURACAO_CADASTRO_SEG}s)...")
        try:
            chunks = gravar_audio_microfone(DURACAO_CADASTRO_SEG)
            encoder = _carregar_encoder()
            embedding = perfil_de_chunks(encoder, chunks)
            if embedding is None:
                notificar("Transkriptor", "Erro: áudio insuficiente para cadastro.")
                self._status("Erro no cadastro de voz.")
                return
            os.makedirs(os.path.dirname(ARQUIVO_PERFIL_VOZ), exist_ok=True)
            salvar_perfil(embedding, ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC)
            self.identificar_minha_voz = True
            cfg = _carregar_config_user()
            cfg["versao_config"] = 2
            cfg["identificar_minha_voz"] = True
            cfg["rotulo_usuario"] = self.rotulo_usuario
            cfg["capturar_mic"] = self.capturar_mic
            _salvar_config_user(cfg)
            notificar("Transkriptor", "Perfil de voz salvo.")
            self._status("Perfil de voz salvo.")
        except Exception as e:
            logging.exception("Erro ao cadastrar voz")
            notificar("Transkriptor", f"Erro no cadastro: {e}")
            self._status(f"Erro no cadastro de voz: {e}")
        self._atualizar_tooltip()

    def alternar_identificar_voz(self, _icone=None, _item=None):
        if not perfil_existe(ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC):
            notificar("Transkriptor", "Cadastre sua voz antes de ativar a identificação.")
            return
        self.identificar_minha_voz = not self.identificar_minha_voz
        cfg = _carregar_config_user()
        cfg["identificar_minha_voz"] = self.identificar_minha_voz
        _salvar_config_user(cfg)
        self._atualizar_tooltip()

    def apagar_perfil_voz(self, _icone=None, _item=None):
        for caminho in (ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC):
            if os.path.isfile(caminho):
                os.remove(caminho)
        self.identificar_minha_voz = False
        cfg = _carregar_config_user()
        cfg["identificar_minha_voz"] = False
        _salvar_config_user(cfg)
        notificar("Transkriptor", "Perfil de voz removido.")
        self._status("Perfil de voz removido.")
        self._atualizar_tooltip()

    def alternar_criptografia(self, _icone=None, _item=None):
        self.criptografar_transcricoes = not self.criptografar_transcricoes
        cfg = _carregar_config_user()
        cfg["criptografar_transcricoes"] = self.criptografar_transcricoes
        _salvar_config_user(cfg)
        if self.criptografar_transcricoes and chave_disponivel():
            migrar_txt_legacy(PASTA_TRANSCRICOES)
            migrar_vozes_legacy(
                ARQUIVO_PERFIL_VOZ,
                ARQUIVO_PERFIL_VOZ_ENC,
                ARQUIVO_VOZES_CONHECIDAS,
                ARQUIVO_VOZES_CONHECIDAS_ENC,
            )
        estado = "ativada" if self.criptografar_transcricoes else "desativada"
        self._status(f"Criptografia de transcricoes {estado}.")
        self._atualizar_tooltip()

    def alternar_startup(self, _icone=None, _item=None):
        """BUG-10: toggle para iniciar com o Windows."""
        self.iniciar_com_windows = not self.iniciar_com_windows
        if self.iniciar_com_windows:
            if _criar_atalho_startup():
                self._status("Iniciar com Windows: ativado.")
                notificar("Transkriptor", "Iniciar com Windows ativado.")
            else:
                self.iniciar_com_windows = False
                self._status("Erro ao criar atalho de startup.")
        else:
            _remover_atalho_startup()
            self._status("Iniciar com Windows: desativado.")
        # persiste a preferência
        cfg = _carregar_config_user()
        cfg["iniciar_com_windows"] = self.iniciar_com_windows
        _salvar_config_user(cfg)
        self._atualizar_tooltip()

    def sair(self, _icone=None, _item=None):
        gravando = self._gravando()
        if confirmacao_saida_necessaria(gravando):
            if not saida_permitida(gravando, self._confirmar_saida()):
                return
        self._parar_transcricao()
        self._modo_manual = False
        if self.icone is not None:
            self.icone.stop()
        liberar_lock()
        logging.info("Transkriptor encerrado.")

    # ---- texto dinamico do menu ----
    def _texto_status(self, _item=None):
        with self._lock:
            if self.transcritor and getattr(self.transcritor, "diarizando", False):
                return "Separando vozes (pós-processamento)..."
            if self.transcritor and self.transcritor.rodando:
                return "Transcrevendo reuniao..."
            if self.deteccao_ativa:
                return "Aguardando Google Meet..."
            return "Deteccao pausada"

    def _texto_deteccao(self, _item=None):
        return "Pausar deteccao automatica" if self.deteccao_ativa else "Retomar deteccao automatica"

    def _texto_diarizacao(self, _item=None):
        return ("Desativar separação de vozes" if self.diarizacao_ativa
                else "Ativar separação de vozes")

    def _texto_criptografia(self, _item=None):
        if self.criptografar_transcricoes:
            return "✓ Criptografar transcrições"
        return "Criptografar transcrições"

    def _texto_startup(self, _item=None):
        return "Iniciar com o Windows" if not self.iniciar_com_windows else "✓ Iniciar com o Windows"

    def _texto_transcricao_manual(self, _item=None):
        return texto_transcricao_manual(self._gravando() and self._modo_manual)

    def _texto_identificar_voz(self, _item=None):
        if self.identificar_minha_voz:
            return f"✓ Identificar minha voz ({self.rotulo_usuario})"
        return "Identificar minha voz"

    def _texto_nomes_meet(self, _item=None):
        if self.usar_nomes_meet:
            return "✓ Identificar nomes do Meet"
        return "Identificar nomes do Meet"

    def _texto_legendas_meet(self, _item=None):
        if self.modo_legendas_meet:
            return "✓ Modo legendas Meet (Tactiq)"
        return "Modo legendas Meet (Tactiq)"

    def alternar_nomes_meet(self, _icone=None, _item=None):
        self.usar_nomes_meet = not self.usar_nomes_meet
        cfg = _carregar_config_user()
        cfg["usar_nomes_meet"] = self.usar_nomes_meet
        _salvar_config_user(cfg)
        if self.usar_nomes_meet and self._meet_bridge_thread is None:
            self._meet_bridge_thread = iniciar_bridge_em_thread(
                self.meet_bridge,
                "127.0.0.1",
                PORTA_MEET_BRIDGE,
            )
            self._status(f"Ponte Meet ativa em 127.0.0.1:{PORTA_MEET_BRIDGE}")
        self._atualizar_tooltip()

    def alternar_legendas_meet(self, _icone=None, _item=None):
        self.modo_legendas_meet = not self.modo_legendas_meet
        cfg = _carregar_config_user()
        cfg["modo_legendas_meet"] = self.modo_legendas_meet
        if self.modo_legendas_meet:
            self.usar_nomes_meet = True
            cfg["usar_nomes_meet"] = True
        _salvar_config_user(cfg)
        if self.usar_nomes_meet and self._meet_bridge_thread is None:
            self._meet_bridge_thread = iniciar_bridge_em_thread(
                self.meet_bridge,
                "127.0.0.1",
                PORTA_MEET_BRIDGE,
            )
            self._status(f"Ponte Meet ativa em 127.0.0.1:{PORTA_MEET_BRIDGE}")
        self._atualizar_tooltip()

    def abrir_extensao_meet(self, _icone=None, _item=None):
        pasta = os.path.join(BASE_DIR, "extension", "meet")
        os.makedirs(pasta, exist_ok=True)
        os.startfile(pasta)

    def renomear_falante_menu(self, _icone=None, _item=None):
        threading.Thread(target=self._renomear_falante_thread, daemon=True).start()

    def _renomear_falante_thread(self):
        from renomear_falante_flow import (
            persistir_renomeacao_falante,
            rotulos_falante_disponiveis,
        )

        t = self.transcritor
        centroides = getattr(t, "_centroides_por_rotulo_ultima", None) if t else None
        if not centroides:
            notificar(
                "Transkriptor",
                "Transcreva e diarize uma reunião antes de renomear um falante.",
            )
            return

        rotulos = rotulos_falante_disponiveis(centroides)
        if not rotulos:
            notificar("Transkriptor", "Nenhum FALANTE_XX disponível na última diarização.")
            return

        try:
            import tkinter as tk
            from tkinter import simpledialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            rotulo = simpledialog.askstring(
                "Renomear falante",
                f"Rótulo a renomear:\n{', '.join(rotulos)}",
                parent=root,
            )
            if not rotulo:
                root.destroy()
                return
            nome = simpledialog.askstring(
                "Renomear falante",
                f"Novo nome para {rotulo.strip().upper()}:",
                parent=root,
            )
            root.destroy()
            if not nome:
                return
            salvo = persistir_renomeacao_falante(rotulo, nome, centroides, ARQUIVO_VOZES_CONHECIDAS)
            notificar("Transkriptor", f"Voz salva como «{salvo}» para próximas reuniões.")
            self._status(f"Voz conhecida salva: {salvo}")
        except ValueError as e:
            notificar("Transkriptor", str(e))
            self._status(f"Erro ao renomear: {e}")
        except Exception as e:
            logging.exception("Erro ao renomear falante")
            notificar("Transkriptor", f"Erro ao renomear: {e}")
            self._status(f"Erro ao renomear: {e}")

    def abrir_vozes_conhecidas(self, _icone=None, _item=None):
        pasta = os.path.dirname(ARQUIVO_VOZES_CONHECIDAS)
        os.makedirs(pasta, exist_ok=True)
        if not os.path.isfile(ARQUIVO_VOZES_CONHECIDAS):
            with open(ARQUIVO_VOZES_CONHECIDAS, "w", encoding="utf-8") as f:
                json.dump({}, f)
        os.startfile(pasta)

    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem(self._texto_status, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir pasta de transcricoes", self.abrir_pasta),
            pystray.MenuItem("Abrir log", self.abrir_log),
            pystray.MenuItem(self._texto_transcricao_manual, self.alternar_transcricao_manual),
            pystray.MenuItem("Abrir assistente (resumo, perguntas)", self.abrir_assistente),
            pystray.MenuItem(self._texto_deteccao, self.alternar_deteccao),
            pystray.MenuItem(self._texto_diarizacao, self.alternar_diarizacao),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Cadastrar minha voz (20s)", self.cadastrar_minha_voz),
            pystray.MenuItem(self._texto_identificar_voz, self.alternar_identificar_voz),
            pystray.MenuItem("Apagar perfil de voz", self.apagar_perfil_voz),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._texto_nomes_meet, self.alternar_nomes_meet),
            pystray.MenuItem(self._texto_legendas_meet, self.alternar_legendas_meet),
            pystray.MenuItem("Instalar extensão Meet (pasta)", self.abrir_extensao_meet),
            pystray.MenuItem("Renomear falante (última diarização)", self.renomear_falante_menu),
            pystray.MenuItem("Abrir pasta vozes conhecidas", self.abrir_vozes_conhecidas),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._texto_criptografia, self.alternar_criptografia),
            pystray.MenuItem(self._texto_startup, self.alternar_startup),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self.sair),
        )

    def _ao_bandeja_pronta(self, icon):
        """Registra o ícone e inicia serviços uma vez após prontidão Win32."""
        try:
            icon.visible = True
            with self._lock:
                if self._bandeja_pronta:
                    return
                self._bandeja_pronta = True

            if self.usar_nomes_meet:
                self._meet_bridge_thread = iniciar_bridge_em_thread(
                    self.meet_bridge,
                    "127.0.0.1",
                    PORTA_MEET_BRIDGE,
                )
                logging.info("Ponte Meet iniciada em 127.0.0.1:%s", PORTA_MEET_BRIDGE)

            self._monitor_thread = threading.Thread(
                target=self._monitorar_meet,
                daemon=True,
                name="Transkriptor-MonitorMeet",
            )
            self._monitor_thread.start()
            logging.info("Bandeja pronta.")
            logging.info("Monitor do Meet iniciado.")
            notificar(
                "Transkriptor",
                "Ativo na bandeja. Se o ícone não aparecer, clique em ^ na barra de tarefas.",
            )
            try:
                icon.notify(
                    "Ícone na bandeja do sistema. Use ^ se estiver oculto.",
                    "Transkriptor ativo",
                )
            except Exception:
                logging.warning("Notificação nativa da bandeja indisponível.")
        except Exception:
            logging.exception("Falha ao preparar bandeja")
            with self._lock:
                self._bandeja_pronta = False
            _mostrar_erro_fatal("Não foi possível preparar a bandeja do Transkriptor.")
            icon.stop()

    def rodar(self):
        criar_ico()
        # Sincroniza atalho de startup com a preferência carregada
        if self.iniciar_com_windows and not _startup_ativo():
            _criar_atalho_startup()
        elif not self.iniciar_com_windows and _startup_ativo():
            _remover_atalho_startup()
        self.icone = pystray.Icon(
            "Transkriptor",
            icon=criar_imagem(),
            title=f"Transkriptor {VERSAO} - Aguardando Meet",
            menu=self._menu(),
        )
        try:
            self.icone.run(setup=self._ao_bandeja_pronta)
        finally:
            liberar_lock()


def _mostrar_erro_fatal(msg):
    logging.exception(msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            msg + f"\n\nVeja o log:\n{LOG_FILE}",
            "Transkriptor — erro ao iniciar",
            0x10,
        )
    except Exception:
        pass


if __name__ == "__main__":
    if not adquirir_lock(LOCK_FILE):
        logging.info("Segunda instancia bloqueada pelo mutex.")
        for _h in logging.root.handlers:
            try:
                _h.flush()
            except Exception:
                pass
        notificar("Transkriptor", "Já está em execução na bandeja do sistema.")
        sys.exit(0)
    try:
        AppTranskriptor().rodar()
    except Exception as e:
        liberar_lock()
        _mostrar_erro_fatal(f"Não foi possível iniciar o Transkriptor:\n{e}")
