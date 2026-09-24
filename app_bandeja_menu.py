# -*- coding: utf-8 -*-
"""Itens de menu e toggles da bandeja (parte do AppTranskriptor)."""

from __future__ import annotations

import json
import logging
import os
import threading

import pystray

from confirmacoes import confirmar_na_bandeja
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
from crypto_storage import chave_disponivel, migrar_vozes_legacy, perfil_existe
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
)
from transkriptor_lock import liberar_lock
from transkriptor_menu_flows import (
    abrir_central,
    iniciar_assistente_ui,
    iniciar_retranscricao_ui,
    rodar_diagnostico_ui,
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

    def _confirmar_saida(self):
        return confirmar_na_bandeja("sair_gravando")

    def abrir_assistente(self, _icone=None, _item=None):
        threading.Thread(target=iniciar_assistente_ui, args=(self,), daemon=True).start()

    def abrir_central(self, _icone=None, _item=None):
        """UX-14.D2: a Central é a interface principal; a bandeja lança e indica."""
        abrir_central(self, "inicio")

    def abrir_diagnostico(self, _icone=None, _item=None):
        threading.Thread(target=rodar_diagnostico_ui, args=(self,), daemon=True).start()

    def _confirmar_pausa_padrao(self) -> bool:
        # UX-14.E4: mesmo texto da Central; caixa indisponível = não pausa.
        return confirmar_na_bandeja("pausar_gravacao")

    def alternar_deteccao(self, _icone=None, _item=None):
        # pystray só aceita ações com até dois parâmetros; a Central usa `_com`.
        self.alternar_deteccao_com()

    def alternar_deteccao_com(self, confirmar=None):
        if deve_confirmar_pausa(self.deteccao_ativa):
            confirmar = confirmar or getattr(self, "_confirmar_pausa", None) or self._confirmar_pausa_padrao
            if not confirmar():
                return
        with self._lock:
            self.deteccao_ativa = not self.deteccao_ativa
            pausada = not self.deteccao_ativa
        if pausada:
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

        ok = cadastrar_perfil_voz(
            on_status=self._status,
            notificar_fn=notificar,
            finalidade="identificar a sua voz nas suas reuniões",
            consentimento=True,
        )
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
        # UX-14.E4: ação irreversível pede confirmação também na bandeja.
        self.apagar_perfil_voz_com(confirmar=lambda: confirmar_na_bandeja("apagar_perfil_voz"))

    def apagar_perfil_voz_com(self, confirmar=None):
        import config_user

        if confirmar is not None and not confirmar():
            return
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

            def _marcado(item=None, n=nome):
                return getattr(self, "modelo_whisper", MODELO_WHISPER) == n

            itens.append(pystray.MenuItem(nome, _fazer_acao(), checked=_marcado, radio=True))
        return pystray.Menu(*itens)

    def alternar_criptografia(self, _icone=None, _item=None):
        import config_user

        self.criptografar_transcricoes = not self.criptografar_transcricoes
        cfg = config_user.carregar()
        cfg["criptografar_transcricoes"] = self.criptografar_transcricoes
        config_user.salvar(cfg)
        if self.criptografar_transcricoes and chave_disponivel():
            migrar_vozes_legacy(
                ARQUIVO_PERFIL_VOZ,
                ARQUIVO_PERFIL_VOZ_ENC,
                ARQUIVO_VOZES_CONHECIDAS,
                ARQUIVO_VOZES_CONHECIDAS_ENC,
            )
        estado = "ativada" if self.criptografar_transcricoes else "desativada"
        self._status(f"Cópia criptografada {estado}.")
        self._atualizar_tooltip()

    def _confirmar_modo_protegido(self):
        return confirmar_na_bandeja("modo_protegido")

    def ativar_modo_protegido(self, _icone=None, _item=None):
        self.ativar_modo_protegido_com()

    def ativar_modo_protegido_com(self, confirmar=None):
        import config_user
        from politica_privacidade import ProtectionMode, modo_efetivo

        if modo_efetivo() == ProtectionMode.PROTECTED:
            self._status("Modo protegido já está ativo.")
            return
        if self._gravando() or self._processamento_em_execucao():
            self._status("Aguarde o fim da gravação e do processamento para mudar a proteção.")
            return
        if not chave_disponivel():
            self._status("Chave de proteção indisponível. Modo não alterado.")
            return
        if not (confirmar or self._confirmar_modo_protegido)():
            return
        config_user.atualizar(protection_mode=ProtectionMode.PROTECTED.value)
        self._status("Modo protegido ativado para novas reuniões. Arquivos existentes preservados.")
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
        if self.icone is not None:
            self.icone.stop()
        liberar_lock()
        logging.info("Transkriptor encerrado.")

    def _texto_status(self, _item=None):
        """UX-14.E2: primeira linha do menu com o mesmo vocabulário da Central."""
        # Sem lock: o pystray monta o menu a partir daqui e só lê atributos.
        # Esperar por `self._lock` no desenho do menu transformaria qualquer
        # operação lenta em bandeja congelada.
        from app_estado_ui import ROTULOS

        transcritor = self.transcritor
        if transcritor and getattr(transcritor, "diarizando", False):
            return ROTULOS["separando_vozes"]
        if transcritor and transcritor.rodando:
            fontes = ", ".join(
                getattr(getattr(self, "detector", None), "fontes_da_reuniao", None) or []
            )
            return f"{ROTULOS['gravando']} · {fontes}" if fontes else ROTULOS["gravando"]
        estado = getattr(self, "_estado_processamento", None)
        if estado:
            return f"{ROTULOS['processando']} · {estado}"
        if not self.deteccao_ativa:
            return f"{ROTULOS['pausado']} · não grava reuniões"
        return f"{ROTULOS['aguardando']} · {self._resumo_fontes()}"

    def _resumo_fontes(self):
        """UX-9.1: o menu diz o que o detector está enxergando agora."""
        detector = getattr(self, "detector", None)
        if detector is None:
            return "detector indisponível"
        try:
            ativos = [s.fonte for s in detector.instantaneo() if s.ativo]
        except Exception:
            return "falha ao consultar fontes"
        return f"sinal de: {', '.join(ativos)}" if ativos else "nenhuma reunião à vista"

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
        """UX-14.C3: correção por reunião e aprendizado de voz vivem na Central."""
        abrir_central(self, "participantes")

    def abrir_vozes_conhecidas(self, _icone=None, _item=None):
        pasta = os.path.dirname(ARQUIVO_VOZES_CONHECIDAS)
        os.makedirs(pasta, exist_ok=True)
        if not os.path.isfile(ARQUIVO_VOZES_CONHECIDAS):
            with open(ARQUIVO_VOZES_CONHECIDAS, "w", encoding="utf-8") as f:
                json.dump({}, f)
        os.startfile(pasta)

    def _menu(self):
        # UX-14.D2/E2: ≤ 9 itens de topo, ≤ 2 níveis, estado por `checked` nativo.
        return pystray.Menu(
            pystray.MenuItem(self._texto_status, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir Transkriptor", self.abrir_central, default=True),
            pystray.MenuItem("Gravação automática", self.alternar_deteccao, checked=lambda item: self.deteccao_ativa),
            pystray.MenuItem("Separar vozes", self.alternar_diarizacao, checked=lambda item: self.diarizacao_ativa),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Reuniões",
                pystray.Menu(
                    pystray.MenuItem("Abrir assistente (IA local)", self.abrir_assistente),
                    pystray.MenuItem("Renomear falante e participantes (Central)", self.renomear_falante_menu),
                    pystray.MenuItem("Retranscrever áudio…", self.retranscrever_audio_menu),
                    pystray.MenuItem("Abrir pasta de transcrições", self.abrir_pasta),
                ),
            ),
            pystray.MenuItem(
                "Configurações",
                pystray.Menu(
                    pystray.MenuItem(
                        "Minha voz",
                        pystray.Menu(
                            pystray.MenuItem("Cadastrar minha voz (20s)", self.cadastrar_minha_voz),
                            pystray.MenuItem("Identificar minha voz", self.alternar_identificar_voz, checked=lambda item: self.identificar_minha_voz),
                            pystray.MenuItem("Apagar perfil de voz", self.apagar_perfil_voz),
                            pystray.MenuItem("Abrir pasta vozes conhecidas", self.abrir_vozes_conhecidas),
                        ),
                    ),
                    pystray.MenuItem(
                        "Google Meet",
                        pystray.Menu(
                            pystray.MenuItem("Identificar nomes do Meet", self.alternar_nomes_meet, checked=lambda item: self.usar_nomes_meet),
                            pystray.MenuItem("Modo legendas Meet (Tactiq)", self.alternar_legendas_meet, checked=lambda item: self.modo_legendas_meet),
                            pystray.MenuItem("Instalar extensão Meet (pasta)", self.abrir_extensao_meet),
                        ),
                    ),
                    pystray.MenuItem(
                        "Proteção",
                        pystray.Menu(
                            pystray.MenuItem("Criar cópia criptografada (.tkpt)", self.alternar_criptografia, checked=lambda item: self.criptografar_transcricoes),
                            pystray.MenuItem("Ativar modo protegido para novas reuniões…", self.ativar_modo_protegido),
                        ),
                    ),
                    pystray.MenuItem("Modelo Whisper", self._submenu_modelo_whisper()),
                    pystray.MenuItem("Iniciar com o Windows", self.alternar_startup, checked=lambda item: self.iniciar_com_windows),
                    pystray.MenuItem("Abrir log", self.abrir_log),
                ),
            ),
            pystray.MenuItem("Diagnóstico (por que não está gravando?)", self.abrir_diagnostico),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self.sair),
        )
