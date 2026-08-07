# -*- coding: utf-8 -*-
"""
Transkriptor - app de bandeja (bootstrap + núcleo FR-8.2).
Menu em app_bandeja_menu; startup/voz em módulos dedicados.
"""

import logging
import secrets
import os
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

import pystray

from app_bandeja_menu import MenuBandejaMixin
from app_processamento import ProcessamentoReuniaoMixin
from app_bootstrap import (
    atualizar_config_user as _atualizar_config_user,
    carregar_config_user as _carregar_config_user,
    resolver_identificar_minha_voz as _resolver_identificar_minha_voz,
)
from consentimento_gravacao import pedir_consentimento
from bandeja_icone import criar_ico, criar_imagem, imagem_por_estado
from crypto_storage import (
    chave_disponivel,
    migrar_vozes_legacy,
    perfil_existe,
    recuperar_orfaos_wav,
)
from config import (
    ARQUIVO_PERFIL_VOZ,
    ARQUIVO_PERFIL_VOZ_ENC,
    ARQUIVO_VOZES_CONHECIDAS,
    ARQUIVO_VOZES_CONHECIDAS_ENC,
    BASE_DIR,
    CAPTURAR_MIC,
    HEARTBEAT_MONITOR_CICLOS,
    IDIOMA,
    INTERVALO_MONITOR_MEET,
    LOG_FILE,
    MODELO_WHISPER,
    MODELOS_WHISPER_MENU,
    MODO_LEGENDAS_MEET,
    PASTA_AUDIO,
    PASTA_TRANSCRICOES,
    PORTA_MEET_BRIDGE,
    RETENCAO_AUDIO_DIAS,
    ROTULO_USUARIO,
    USAR_NOMES_MEET,
    VERSAO,
)
from monitor_reuniao import autoteste_audio, construir_detector, texto_heartbeat
from estado_icone import DURACAO_ERRO_ICONE, resolver_estado_icone
from fila_processamento import fila_padrao
from meet_bridge import MeetBridge, iniciar_bridge_em_thread, sincronizar_token_extensao
from notificador import (
    configurar_icone,
    notificar,
)
from retencao_audio import limpar_audios_vencidos
from startup_windows import (
    criar_atalho_startup as _criar_atalho_startup,
    remover_atalho_startup as _remover_atalho_startup,
    startup_ativo as _startup_ativo,
)
from status_seguro import sanitizar_para_log
from transkriptor_acoes import (
    deve_iniciar_gravacao_auto,
    deve_parar_transcricao_por_meet,
    deve_toast_meet_em_pausa,
)
from transkriptor_lock import adquirir_lock, liberar_lock
from watchdog import Watchdog

os.makedirs(PASTA_TRANSCRICOES, exist_ok=True)
LOCK_FILE = os.path.join(BASE_DIR, "transkriptor.lock")

_log_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.root.setLevel(logging.INFO)
logging.root.addHandler(_log_handler)


class AppTranskriptor(ProcessamentoReuniaoMixin, MenuBandejaMixin):
    def __init__(self):
        self.icone = None
        self.transcritor = None
        self.watchdog = None
        self.deteccao_ativa = True
        self.diarizacao_ativa = True
        self._toast_pausa_reuniao = None
        self._confirmar_pausa = self._confirmar_pausa_padrao
        self._recusa_reuniao_ativa = False
        self._consentimento_em_andamento = False
        cfg = _carregar_config_user()
        self.modelo_whisper = cfg.get("modelo_whisper", MODELO_WHISPER)
        if self.modelo_whisper not in MODELOS_WHISPER_MENU:
            self.modelo_whisper = MODELO_WHISPER
        self.iniciar_com_windows = cfg.get("iniciar_com_windows", _startup_ativo())
        self.criptografar_transcricoes = cfg.get("criptografar_transcricoes", True)
        if self.criptografar_transcricoes and chave_disponivel():
            vozes = migrar_vozes_legacy(
                ARQUIVO_PERFIL_VOZ,
                ARQUIVO_PERFIL_VOZ_ENC,
                ARQUIVO_VOZES_CONHECIDAS,
                ARQUIVO_VOZES_CONHECIDAS_ENC,
            )
            if vozes:
                logging.info("Migrados %d arquivos de voz legados para .enc", vozes)
            orfaos_enc = recuperar_orfaos_wav(PASTA_AUDIO)
            if orfaos_enc:
                logging.info("Criptografados %d audios orfaos em PASTA_AUDIO", orfaos_enc)
        if "criptografar_transcricoes" not in cfg:
            _atualizar_config_user(
                criptografar_transcricoes=self.criptografar_transcricoes
            )
        tem_perfil = perfil_existe(ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC)
        antes = cfg.get("identificar_minha_voz")
        self.identificar_minha_voz, cfg = _resolver_identificar_minha_voz(cfg, tem_perfil)
        if antes and not tem_perfil:
            _atualizar_config_user(identificar_minha_voz=False)
        self.rotulo_usuario = cfg.get("rotulo_usuario", ROTULO_USUARIO)
        self.capturar_mic = cfg.get("capturar_mic", CAPTURAR_MIC)
        self.usar_nomes_meet = cfg.get("usar_nomes_meet", USAR_NOMES_MEET)
        self.modo_legendas_meet = cfg.get("modo_legendas_meet", MODO_LEGENDAS_MEET)
        cfg_meet = _carregar_config_user()
        meet_token = cfg_meet.get("meet_bridge_token")
        if not meet_token:
            meet_token = secrets.token_urlsafe(24)
            _atualizar_config_user(meet_bridge_token=meet_token)
        self.meet_bridge = MeetBridge(token=meet_token)
        sincronizar_token_extensao(meet_token, BASE_DIR)
        # FR-9.B1: fusão de fontes. Qualquer uma mantém a reunião viva; assim
        # trocar de aba no meio da chamada não encerra mais a gravação.
        self.detector = construir_detector(self.meet_bridge)
        self._meet_bridge_thread = None
        self._monitor_thread = None
        self._bandeja_pronta = False
        self._inicio_transcricao_wall_ms = None
        self.ultimo_status = "Aguardando Google Meet..."
        self.ultimo_log = ""
        self._lock = threading.Lock()
        self._em_erro = False
        self._instante_erro = None
        self._iniciando = False
        self.fila = fila_padrao()
        self._worker_processamento = None
        self._estado_processamento = None
        self._ultimo_job_id = None

    def _gravando(self):
        return bool(self.transcritor and self.transcritor.rodando)

    def _status(self, msg):
        with self._lock:
            self.ultimo_log = msg
        logging.info(sanitizar_para_log(msg))
        self._atualizar_tooltip()

    def _atualizar_tooltip(self):
        if self.icone is None:
            return
        estado_icone, estado = resolver_estado_icone(
            self.transcritor,
            self.deteccao_ativa,
            em_erro=self._em_erro,
            instante_erro=self._instante_erro,
            processando=self._processamento_em_execucao(),
        )
        if self._em_erro and estado_icone != "erro":
            self._em_erro = False
            self._instante_erro = None
        self.icone.title = f"Transkriptor {VERSAO} - {estado}"
        try:
            self.icone.icon = imagem_por_estado(estado_icone)
        except Exception:
            pass
        self.icone.update_menu()

    def _eventos_meet_relativos(self):
        if self._inicio_transcricao_wall_ms is None:
            return []
        inicio = self._inicio_transcricao_wall_ms
        relativos = []
        for ev in self.meet_bridge.drenar_eventos():
            ts_ms = ev.get("ts_ms", int(ev.get("ts_sec", 0) * 1000))
            relativos.append({**ev, "ts_sec": (ts_ms - inicio) / 1000.0})
        return relativos

    def _iniciar_transcricao(self):
        with self._lock:
            # Pausar enquanto a caixa de consentimento estava aberta não pode
            # abrir captura depois que o usuário clicar em Sim.
            if not getattr(self, "deteccao_ativa", True):
                return
            # Um único portão impede duas capturas simultâneas no loopback.
            if getattr(self, "_iniciando", False) or (
                self.transcritor and self.transcritor.rodando
            ):
                return
            self._iniciando = True
        try:
            self._iniciar_transcricao_interno()
        finally:
            with self._lock:
                self._iniciando = False

    def _iniciar_transcricao_interno(self):
        from transcricao_core import Transcritor

        self._inicio_transcricao_wall_ms = int(time.time() * 1000)
        detector = getattr(self, "detector", None)
        fontes = ", ".join(getattr(detector, "fontes_da_reuniao", None) or []) or "?"
        self._status(f"Reunião detectada ({fontes}). Iniciando gravação...")
        self.transcritor = Transcritor(
            modelo=getattr(self, "modelo_whisper", MODELO_WHISPER),
            idioma=IDIOMA,
            pasta_saida=PASTA_TRANSCRICOES,
            diarizar_ao_final=self.diarizacao_ativa,
            on_status=self._status,
            capturar_mic=self.capturar_mic,
            identificar_voz=self.identificar_minha_voz
            and perfil_existe(ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC),
            rotulo_usuario=self.rotulo_usuario,
            criptografar=self.criptografar_transcricoes,
            processar_ao_vivo=False,
        )
        try:
            # O teste e o start ficam sob o mesmo lock da ação Pausar. Assim a
            # pausa não pode passar entre a validação e a abertura do áudio.
            with self._lock:
                if not getattr(self, "deteccao_ativa", True):
                    self.transcritor = None
                    return
                self.transcritor.start()
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
            t, w = self.transcritor, self.watchdog
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
            with self._lock:
                if self.transcritor is t:
                    self.transcritor = None
            if caminho:
                self._enfileirar_reuniao(t, caminho)
            self._atualizar_tooltip()

    def _em_thread(self, alvo, nome):
        """Executa fora da thread do monitor.

        Carregar o Whisper e finalizar a diarização levam dezenas de segundos.
        Rodando no monitor, a detecção ficava cega justamente durante o início e
        o fim da reunião.
        """
        threading.Thread(target=alvo, daemon=True, name=nome).start()

    def _processar_mudanca_meet(self, mudanca):
        if mudanca == "iniciou":
            if deve_iniciar_gravacao_auto(self._recusa_reuniao_ativa):
                with self._lock:
                    if self._consentimento_em_andamento:
                        return
                    self._consentimento_em_andamento = True
                self._em_thread(self._pedir_e_iniciar, "Transkriptor-Consentimento")
            return
        if mudanca == "encerrou":
            # FR-2.10: recusa vale só para a reunião que acabou
            self._recusa_reuniao_ativa = False
        if deve_parar_transcricao_por_meet(mudanca):
            self._status("Reunião encerrada. Finalizando transcricao...")
            self._em_thread(self._parar_transcricao, "Transkriptor-Fim")

    def _pedir_e_iniciar(self):
        """Solicita consentimento antes de abrir dispositivo ou arquivo de áudio."""
        try:
            perguntar = getattr(self, "_pedir_consentimento", None) or pedir_consentimento
            autorizado = bool(perguntar())
            detector = getattr(self, "detector", None)
            reuniao_ainda_ativa = bool(
                detector is not None and getattr(detector, "reuniao_ativa", False)
            )
            if not autorizado:
                if reuniao_ainda_ativa:
                    self._recusa_reuniao_ativa = True
                    self._status("Esta reunião não será gravada.")
                return
            if not reuniao_ainda_ativa:
                return
            if not getattr(self, "deteccao_ativa", True):
                self._status("Detecção pausada; reunião não será gravada.")
                return
            self._iniciar_transcricao()
        finally:
            with self._lock:
                self._consentimento_em_andamento = False

    def _detectar_mudanca_meet(self):
        return self.detector.verificar()

    def _heartbeat_monitor(self, ciclos):
        """FR-9.C4: prova periódica no log de que o monitor continua vivo."""
        if ciclos % HEARTBEAT_MONITOR_CICLOS:
            return
        logging.info("%s", texto_heartbeat(self.detector, self._gravando(), ciclos))

    def _monitorar_meet(self):
        ciclos = 0
        while True:
            try:
                ciclos += 1
                mudanca = self._detectar_mudanca_meet()
                self._heartbeat_monitor(ciclos)
                if self.deteccao_ativa:
                    self._processar_mudanca_meet(mudanca)
                else:
                    if deve_toast_meet_em_pausa(
                        self.deteccao_ativa, mudanca, self._toast_pausa_reuniao is not None
                    ):
                        self._toast_pausa_reuniao = mudanca
                        notificar(
                            "Transkriptor",
                            "Reunião detectada, mas a gravação está pausada",
                        )
                    if mudanca == "encerrou":
                        self._toast_pausa_reuniao = None
            except Exception:
                logging.exception("Erro no monitor de reunião")
            time.sleep(INTERVALO_MONITOR_MEET)

    def _autoteste_audio(self):
        """FR-9.A4: falha de captura vira aviso visível, nunca silêncio no log."""
        autoteste_audio(self._erro_critico)

    def _rodar_retencao_audio(self):
        try:
            _removidos, orfaos = limpar_audios_vencidos(
                PASTA_AUDIO, PASTA_TRANSCRICOES, dias=RETENCAO_AUDIO_DIAS
            )
            if orfaos:
                notificar(
                    "Transkriptor",
                    f"{len(orfaos)} áudio(s) antigo(s) sem transcrição — "
                    "use Retranscrever áudio no menu.",
                )
        except Exception:
            logging.exception("Falha na retenção de áudios")

    def _loop_retencao_audio(self):
        while True:
            self._rodar_retencao_audio()
            time.sleep(24 * 3600)

    def _ao_bandeja_pronta(self, icon):
        try:
            icon.visible = True
            with self._lock:
                if self._bandeja_pronta:
                    return
                self._bandeja_pronta = True

            threading.Thread(
                target=self._preparar_processamento,
                daemon=True,
                name="Transkriptor-FilaProcessamento",
            ).start()

            threading.Thread(
                target=self._loop_retencao_audio,
                daemon=True,
                name="Transkriptor-RetencaoAudio",
            ).start()

            # FR-9.3: a ponte agora também é fonte de detecção, então sobe
            # sempre — não só quando "Identificar nomes do Meet" está ligado.
            # Se ela falhar (porta ocupada), a bandeja continua: título e
            # microfone seguem detectando reuniões sem a extensão.
            bridge = getattr(self, "meet_bridge", None)
            if bridge is not None:
                try:
                    self._meet_bridge_thread = iniciar_bridge_em_thread(
                        bridge, "127.0.0.1", PORTA_MEET_BRIDGE
                    )
                    logging.info(
                        "Ponte Meet iniciada em 127.0.0.1:%s", PORTA_MEET_BRIDGE
                    )
                except Exception:
                    logging.exception("Ponte Meet indisponível; detecção segue sem ela")

            threading.Thread(
                target=self._autoteste_audio, daemon=True, name="Transkriptor-AutoTeste"
            ).start()

            self._monitor_thread = threading.Thread(
                target=self._monitorar_meet, daemon=True, name="Transkriptor-MonitorMeet"
            )
            self._monitor_thread.start()
            logging.info("Bandeja pronta.")
            logging.info("Monitor do Meet iniciado.")
        except Exception:
            logging.exception("Falha ao preparar bandeja")
            with self._lock:
                self._bandeja_pronta = False
            _mostrar_erro_fatal("Não foi possível preparar a bandeja do Transkriptor.")
            icon.stop()

    def rodar(self):
        criar_ico()
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
        configurar_icone(self.icone)
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
    if not adquirir_lock(LOCK_FILE, usar_mutex_nomeado=True):
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
