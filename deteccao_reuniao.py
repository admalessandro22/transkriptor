# -*- coding: utf-8 -*-
"""Detecção de reunião por fontes independentes, com fusão OR (FR-9.1).

Uma fonte só nunca foi suficiente:

* **título da janela** enxerga só a aba em primeiro plano — trocar de aba no meio
  da reunião parecia "reunião encerrada";
* **microfone em uso** cobre aba em segundo plano, janela minimizada, Zoom e
  Teams, mas demora a soltar e não distingue chamada de ditado;
* **ponte da extensão** é a única que sabe de verdade, mas exige instalar a
  extensão.

A fusão resolve o conjunto: qualquer fonte **mantém** a reunião viva (some o
falso "encerrou" ao trocar de aba); para **iniciar**, uma fonte forte basta e uma
fonte fraca precisa se sustentar por mais ciclos (some o falso positivo de um
`chrome.exe` que abriu o microfone por dez segundos para um áudio de WhatsApp).
"""

from __future__ import annotations

import logging

from config import (
    CONFIRMACAO_FIM_REUNIAO,
    CONFIRMACAO_INICIO_FRACA,
    CONFIRMACAO_INICIO_MEET,
)

logger = logging.getLogger(__name__)


class Sinal:
    """Leitura instantânea de uma fonte de detecção."""

    __slots__ = ("fonte", "ativo", "forte", "detalhe")

    def __init__(self, fonte, ativo, forte=False, detalhe=""):
        self.fonte = fonte
        self.ativo = bool(ativo)
        self.forte = bool(forte) and bool(ativo)
        self.detalhe = detalhe

    def __repr__(self):  # pragma: no cover - só para depuração
        return f"Sinal({self.fonte!r}, ativo={self.ativo}, forte={self.forte})"


class FonteTitulo:
    """Reunião reconhecida pelo título de alguma janela aberta."""

    nome = "titulo"

    def __init__(self, obter_janelas, exigir_janela_visivel=False):
        self._obter_janelas = obter_janelas
        self._exigir_janela_visivel = exigir_janela_visivel

    def ler(self):
        from detector_meet import classificar_titulo

        try:
            janelas = list(self._obter_janelas() or [])
        except Exception:  # noqa: BLE001
            logger.debug("Falha ao listar janelas", exc_info=True)
            return Sinal(self.nome, False, detalhe="falha ao listar janelas")
        melhor, titulo_casado = "", ""
        for janela in janelas:
            if isinstance(janela, dict):
                titulo = janela.get("titulo", "")
                visivel = janela.get("visivel", True)
            else:
                titulo, visivel = janela, True
            if self._exigir_janela_visivel and not visivel:
                continue
            classe = classificar_titulo(titulo)
            if classe == "forte":
                return Sinal(self.nome, True, forte=True, detalhe=str(titulo))
            if classe and not melhor:
                melhor, titulo_casado = classe, str(titulo)
        if melhor:
            return Sinal(self.nome, True, forte=True, detalhe=titulo_casado)
        return Sinal(self.nome, False, detalhe=f"{len(janelas)} janela(s) sem reunião")


class FonteMicrofone:
    """Reunião inferida de um app de conferência segurando o microfone.

    Fonte **fraca** de início: sozinha, precisa de mais ciclos para confirmar.
    Mas mantém a reunião viva sozinha, que é o que conserta a troca de aba.
    """

    nome = "microfone"

    def __init__(self, consultar=None):
        if consultar is None:
            from monitor_microfone import microfone_em_uso_por_conferencia

            consultar = microfone_em_uso_por_conferencia
        self._consultar = consultar

    def ler(self):
        try:
            apps = list(self._consultar() or [])
        except Exception:  # noqa: BLE001
            logger.debug("Falha ao consultar microfone", exc_info=True)
            return Sinal(self.nome, False, detalhe="consulta indisponível")
        if apps:
            return Sinal(self.nome, True, forte=False, detalhe=", ".join(apps))
        return Sinal(self.nome, False, detalhe="nenhum app de conferência com microfone")


class FontePonte:
    """Estado informado pela extensão do Meet — a fonte mais confiável."""

    nome = "extensao"

    def __init__(self, bridge):
        self._bridge = bridge

    def ler(self):
        bridge = self._bridge
        if bridge is None:
            return Sinal(self.nome, False, detalhe="ponte desligada")
        try:
            ativo = bool(bridge.reuniao_ativa())
        except Exception:  # noqa: BLE001
            logger.debug("Falha ao ler estado da ponte", exc_info=True)
            return Sinal(self.nome, False, detalhe="ponte indisponível")
        if ativo:
            return Sinal(self.nome, True, forte=True, detalhe="extensão reportou reunião")
        return Sinal(self.nome, False, detalhe="sem sinal da extensão")


def fundir(sinais):
    """Reduz os sinais a `(algum_ativo, algum_forte, fontes_ativas)`."""
    ativos = [s for s in sinais if s.ativo]
    return (
        bool(ativos),
        any(s.forte for s in ativos),
        [s.fonte for s in ativos],
    )


class DetectorReuniao:
    """Debounce assimétrico sobre a fusão das fontes.

    * início por fonte forte: `confirma_inicio` ciclos;
    * início só por fonte fraca: `confirma_inicio_fraca` ciclos;
    * fim: `confirma_fim` ciclos sem **nenhuma** fonte ativa.

    O fim é deliberadamente mais lento que o início: perder o fim de uma reunião
    custa alguns segundos de áudio a mais no arquivo; cortar no meio custa a
    reunião inteira.
    """

    def __init__(
        self,
        fontes,
        confirma_inicio=CONFIRMACAO_INICIO_MEET,
        confirma_inicio_fraca=CONFIRMACAO_INICIO_FRACA,
        confirma_fim=CONFIRMACAO_FIM_REUNIAO,
    ):
        self.fontes = list(fontes)
        self.confirma_inicio = confirma_inicio
        self.confirma_inicio_fraca = confirma_inicio_fraca
        self.confirma_fim = confirma_fim
        self._contagem_forte = 0
        self._contagem_fraca = 0
        self._contagem_fim = 0
        self._ativa = False
        self.ultimos_sinais: list[Sinal] = []
        self.fontes_da_reuniao: list[str] = []

    @property
    def reuniao_ativa(self):
        return self._ativa

    # compatibilidade com o nome antigo usado pelo app de bandeja
    @property
    def meet_ativo(self):
        return self._ativa

    def instantaneo(self):
        """Lê todas as fontes agora (usado pelo diagnóstico da bandeja)."""
        sinais = []
        for fonte in self.fontes:
            try:
                sinais.append(fonte.ler())
            except Exception:  # noqa: BLE001
                logger.debug("Fonte %s falhou", getattr(fonte, "nome", "?"), exc_info=True)
                sinais.append(Sinal(getattr(fonte, "nome", "?"), False, detalhe="erro na fonte"))
        return sinais

    def verificar(self):
        """Um ciclo do monitor. Retorna "iniciou" | "encerrou" | None."""
        sinais = self.instantaneo()
        self.ultimos_sinais = sinais
        algum, forte, fontes_ativas = fundir(sinais)
        return self._processar(algum, forte, fontes_ativas)

    def _processar(self, algum, forte, fontes_ativas):
        if algum:
            self._contagem_fim = 0
            self._contagem_fraca += 1
            self._contagem_forte = self._contagem_forte + 1 if forte else 0
        else:
            self._contagem_forte = 0
            self._contagem_fraca = 0
            self._contagem_fim += 1

        if not self._ativa:
            confirmou_forte = self._contagem_forte >= self.confirma_inicio
            confirmou_fraca = self._contagem_fraca >= self.confirma_inicio_fraca
            if confirmou_forte or confirmou_fraca:
                self._ativa = True
                self.fontes_da_reuniao = list(fontes_ativas)
                logger.info(
                    "Reunião confirmada por %s (%s).",
                    ", ".join(fontes_ativas) or "?",
                    "sinal forte" if confirmou_forte else "sinal sustentado",
                )
                return "iniciou"
            return None

        if self._contagem_fim >= self.confirma_fim:
            self._ativa = False
            self.fontes_da_reuniao = []
            logger.info("Reunião encerrada após %d ciclos sem sinal.", self._contagem_fim)
            return "encerrou"
        return None
