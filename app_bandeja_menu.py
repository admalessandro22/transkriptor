# -*- coding: utf-8 -*-
"""Itens de menu e toggles da bandeja (parte do AppTranskriptor)."""

from __future__ import annotations

import json
import logging
import os
import threading

import pystray

from config import (
    ARQUIVO_PERFIL_VOZ,
    ARQUIVO_PERFIL_VOZ_ENC,
    ARQUIVO_VOZES_CONHECIDAS,
    ARQUIVO_VOZES_CONHECIDAS_ENC,
    BASE_DIR,
    LOG_FILE,
    MODELO_WHISPER,
    MODELOS_WHISPER_MENU,
    PASTA_TRANSCRICOES,
    PORTA_MEET_BRIDGE,
)
from crypto_storage import chave_disponivel, migrar_txt_legacy, migrar_vozes_legacy, perfil_existe
from meet_bridge import iniciar_bridge_em_thread
from notificador import notificar
from perfil_voz_flow import (
    apagar_arquivos_perfil,
    ativar_identificacao_apos_cadastro,
    cadastrar_perfil_voz,
    desativar_perfil_na_config,
)
from startup_windows import (
    criar_atalho_startup as _criar_atalho_startup,
    remover_atalho_startup as _remover_atalho_startup,
)
from transkriptor_acoes import (
    confirmacao_saida_necessaria,
    deve_confirmar_pausa,
    saida_permitida,
    texto_deteccao_menu,
    texto_transcricao_manual,
)
from transkriptor_lock import liberar_lock
from transkriptor_menu_flows import (
    iniciar_assistente_ui,
    iniciar_renomear_falante_ui,
    iniciar_retranscricao_ui,
)


class MenuBandejaMixin:
    """Ações e textos do menu da bandeja."""

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

    def retranscrever_audio_menu(self, _icone=None, _item=None):
        iniciar_retranscricao_ui(self)

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

            return (
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "Transcricao em andamento. Parar e sair?",
                    "Transkriptor",
                    0x00000004 | 0x00000030,
                )
                == 6
            )
        except Exception:
            return False

    def abrir_assistente(self, _icone=None, _item=None):
        threading.Thread(target=iniciar_assistente_ui, args=(self,), daemon=True).start()

    def _confirmar_pausa_padrao(self) -> bool:
        try:
            import ctypes

            return (
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "O Transkriptor NÃO gravará reuniões enquanto pausado. Continuar?",
                    "Transkriptor",
                    0x34,
                )
                == 6
            )
        except Exception:
            return True

    def alternar_deteccao(self, _icone=None, _item=None):
        if deve_confirmar_pausa(self.deteccao_ativa):
            confirmar = getattr(self, "_confirmar_pausa", None) or self._confirmar_pausa_padrao
            if not confirmar():
                return
        self.deteccao_ativa = not self.deteccao_ativa
        if not self.deteccao_ativa:
            self._parar_transcricao()
            self._toast_pausa_reuniao = None
            self._status("Gravação automática pausada.")
        else:
            self._toast_pausa_reuniao = None
            self._status("Gravação automática retomada.")
        self._atualizar_tooltip()

    def alternar_diarizacao(self, _icone=None, _item=None):
        self.diarizacao_ativa = not self.diarizacao_ativa
        estado = "ativa" if self.diarizacao_ativa else "desativada"
        self._status(f"Separação de vozes {estado}.")
        self._atualizar_tooltip()

    def cadastrar_minha_voz(self, _icone=None, _item=None):
        threading.Thread(target=self._cadastrar_voz_thread, daemon=True).start()

    def _cadastrar_voz_thread(self):
        import config_user

        ok = cadastrar_perfil_voz(on_status=self._status, notificar_fn=notificar)
        if ok:
            self.identificar_minha_voz = True
            ativar_identificacao_apos_cadastro(
                config_user.carregar,
                config_user.salvar,
                self.rotulo_usuario,
                self.capturar_mic,
            )
        self._atualizar_tooltip()

    def alternar_identificar_voz(self, _icone=None, _item=None):
        import config_user

        if not perfil_existe(ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC):
            notificar("Transkriptor", "Cadastre sua voz antes de ativar a identificação.")
            return
        self.identificar_minha_voz = not self.identificar_minha_voz
        cfg = config_user.carregar()
        cfg["identificar_minha_voz"] = self.identificar_minha_voz
        config_user.salvar(cfg)
        self._atualizar_tooltip()

    def apagar_perfil_voz(self, _icone=None, _item=None):
        import config_user

        apagar_arquivos_perfil()
        self.identificar_minha_voz = False
        desativar_perfil_na_config(config_user.carregar, config_user.salvar)
        notificar("Transkriptor", "Perfil de voz removido.")
        self._status("Perfil de voz removido.")
        self._atualizar_tooltip()

    def definir_modelo_whisper(self, _icone=None, modelo=None):
        if modelo is None or modelo not in MODELOS_WHISPER_MENU:
            return
        self.modelo_whisper = modelo
        import config_user

        config_user.atualizar(modelo_whisper=modelo)
        msg = f"Modelo Whisper: {modelo} — vale a partir da próxima transcrição"
        self._status(msg)
        notificar("Transkriptor", msg)
        self._atualizar_tooltip()

    def _submenu_modelo_whisper(self):
        itens = []
        for nome in MODELOS_WHISPER_MENU:

            def _fazer_acao(n=nome):
                return lambda icone=None, item=None: self.definir_modelo_whisper(icone, n)

            def _texto(item=None, n=nome):
                marca = "✓ " if getattr(self, "modelo_whisper", MODELO_WHISPER) == n else ""
                return f"{marca}{n}"

            itens.append(pystray.MenuItem(_texto, _fazer_acao(), radio=True))
        return pystray.Menu(*itens)

    def alternar_criptografia(self, _icone=None, _item=None):
        import config_user

        self.criptografar_transcricoes = not self.criptografar_transcricoes
        cfg = config_user.carregar()
        cfg["criptografar_transcricoes"] = self.criptografar_transcricoes
        config_user.salvar(cfg)
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
        import config_user

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
        cfg = config_user.carregar()
        cfg["iniciar_com_windows"] = self.iniciar_com_windows
        config_user.salvar(cfg)
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

    def _texto_status(self, _item=None):
        with self._lock:
            if self.transcritor and getattr(self.transcritor, "diarizando", False):
                return "Separando vozes (pós-processamento)..."
            if self.transcritor and self.transcritor.rodando:
                return "Transcrevendo reuniao..."
            if self.deteccao_ativa:
                return "Aguardando Google Meet..."
            return "PAUSADO — não está gravando"

    def _texto_deteccao(self, _item=None):
        return texto_deteccao_menu(self.deteccao_ativa)

    def _texto_diarizacao(self, _item=None):
        return (
            "Desativar separação de vozes"
            if self.diarizacao_ativa
            else "Ativar separação de vozes"
        )

    def _texto_criptografia(self, _item=None):
        return (
            "✓ Criptografar transcrições"
            if self.criptografar_transcricoes
            else "Criptografar transcrições"
        )

    def _texto_startup(self, _item=None):
        return (
            "✓ Iniciar com o Windows"
            if self.iniciar_com_windows
            else "Iniciar com o Windows"
        )

    def _texto_transcricao_manual(self, _item=None):
        return texto_transcricao_manual(self._gravando() and self._modo_manual)

    def _texto_identificar_voz(self, _item=None):
        if self.identificar_minha_voz:
            return f"✓ Identificar minha voz ({self.rotulo_usuario})"
        return "Identificar minha voz"

    def _texto_nomes_meet(self, _item=None):
        return (
            "✓ Identificar nomes do Meet"
            if self.usar_nomes_meet
            else "Identificar nomes do Meet"
        )

    def _texto_legendas_meet(self, _item=None):
        return (
            "✓ Modo legendas Meet (Tactiq)"
            if self.modo_legendas_meet
            else "Modo legendas Meet (Tactiq)"
        )

    def _garantir_bridge(self):
        if self.usar_nomes_meet and self._meet_bridge_thread is None:
            self._meet_bridge_thread = iniciar_bridge_em_thread(
                self.meet_bridge, "127.0.0.1", PORTA_MEET_BRIDGE
            )
            self._status(f"Ponte Meet ativa em 127.0.0.1:{PORTA_MEET_BRIDGE}")

    def alternar_nomes_meet(self, _icone=None, _item=None):
        import config_user

        self.usar_nomes_meet = not self.usar_nomes_meet
        cfg = config_user.carregar()
        cfg["usar_nomes_meet"] = self.usar_nomes_meet
        config_user.salvar(cfg)
        self._garantir_bridge()
        self._atualizar_tooltip()

    def alternar_legendas_meet(self, _icone=None, _item=None):
        import config_user

        self.modo_legendas_meet = not self.modo_legendas_meet
        cfg = config_user.carregar()
        cfg["modo_legendas_meet"] = self.modo_legendas_meet
        if self.modo_legendas_meet:
            self.usar_nomes_meet = True
            cfg["usar_nomes_meet"] = True
        config_user.salvar(cfg)
        self._garantir_bridge()
        self._atualizar_tooltip()

    def abrir_extensao_meet(self, _icone=None, _item=None):
        pasta = os.path.join(BASE_DIR, "extension", "meet")
        os.makedirs(pasta, exist_ok=True)
        os.startfile(pasta)

    def renomear_falante_menu(self, _icone=None, _item=None):
        threading.Thread(
            target=iniciar_renomear_falante_ui, args=(self,), daemon=True
        ).start()

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
            pystray.MenuItem("Retranscrever áudio…", self.retranscrever_audio_menu),
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
            pystray.MenuItem("Modelo Whisper", self._submenu_modelo_whisper()),
            pystray.MenuItem(self._texto_startup, self.alternar_startup),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self.sair),
        )
