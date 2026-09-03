# -*- coding: utf-8 -*-
"""Detecção de reunião por fontes independentes, com fusão OR (FR-9.1).

Uma fonte só nunca foi suficiente:

* **título da janela** enxerga só a aba em primeiro plano — trocar de aba no meio
  da reunião parecia "reunião encerrada";
* **microfone em uso** é apenas diagnóstico: não distingue reunião de áudio,
  ditado ou WhatsApp e, por isso, nunca pode iniciar uma captura;
* **ponte da extensão** é a única que sabe de verdade, mas exige instalar a
  extensão.

A fusão resolve o conjunto: para **iniciar**, exige uma fonte forte reconhecida;
o sinal fraco permanece exposto apenas para diagnóstico.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from config import (
    CONFIRMACAO_FIM_SEM_SINAL_FORTE,
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
    """Sinal diagnóstico de um app que está usando o microfone."""

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


class FonteZoom:
    """Chamada do Zoom por classe de janela ou microfone corroborado (FR-10.A3).

    O título do Zoom muda com o idioma e com a versão; `FonteTitulo` sozinha
    deixava reuniões inteiras passarem. Ver `detector_zoom`.
    """

    nome = "zoom"

    def __init__(self, listar_janelas=None, consultar_microfone=None):
        if listar_janelas is None:
            from detector_zoom import listar_janelas_com_classe

            listar_janelas = listar_janelas_com_classe
        if consultar_microfone is None:
            from monitor_microfone import microfone_em_uso_por_conferencia

            consultar_microfone = microfone_em_uso_por_conferencia
        self._listar_janelas = listar_janelas
        self._consultar_microfone = consultar_microfone

    def ler(self):
        from detector_zoom import zoom_em_reuniao

        try:
            janelas = list(self._listar_janelas() or [])
            microfones = list(self._consultar_microfone() or [])
        except Exception:  # noqa: BLE001
            logger.debug("Falha ao inspecionar janelas do Zoom", exc_info=True)
            return Sinal(self.nome, False, detalhe="consulta indisponível")
        ativo, motivo = zoom_em_reuniao(janelas, microfones)
        if ativo:
            return Sinal(self.nome, True, forte=True, detalhe=motivo)
        return Sinal(self.nome, False, detalhe="nenhuma chamada do Zoom")


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
            titulo = None
            try:
                titulo = bridge.titulo_meet_atual() if hasattr(bridge, "titulo_meet_atual") else None
            except Exception:
                titulo = None
            detalhe = titulo.strip() if isinstance(titulo, str) and titulo.strip() else "extensão reportou reunião"
            return Sinal(self.nome, True, forte=True, detalhe=detalhe)
        return Sinal(self.nome, False, detalhe="sem sinal da extensão")


_CODIGO_REUNIAO = re.compile(r"^[a-z]{3,4}-[a-z]{3,4}-[a-z]{3,4}$", re.IGNORECASE)
_MAX_SLUG = 40
_NAVEGADORES_RE = r"Google\s+Chrome|Chromium|Microsoft\s+Edge|Mozilla\s+Firefox|Firefox|Brave|Opera|Vivaldi|Safari"


def extrair_titulo_meet(titulo: str | None) -> str | None:
    """Extrai nome amigável de 'Meet: Nome - Google Chrome' (FR-12.A1)."""
    if not titulo or not isinstance(titulo, str):
        return None
    t = titulo.strip()
    if not t:
        return None
    # Tenta "Meet: <nome> [ - Navegador]"
    m = re.match(rf"^Meet\s*:\s*(.+?)\s*(?:[-–—]\s*(?:{_NAVEGADORES_RE})\b.*)?\s*$", t, re.IGNORECASE)
    if m:
        cand = m.group(1).strip()
        if _CODIGO_REUNIAO.match(cand):
            return None
        return cand if len(cand) >= 3 else None
    # Tenta "Meet – <nome> [ - Navegador]" mas não código
    m = re.match(rf"^Meet\s*[-–—]\s*(.+?)\s*(?:[-–—]\s*(?:{_NAVEGADORES_RE})\b.*)?\s*$", t, re.IGNORECASE)
    if m:
        cand = m.group(1).strip()
        # Se for código, não é nome
        if _CODIGO_REUNIAO.match(cand):
            return None
        # Evita "Meet - Google Chrome" que já é filtrado mas garante
        if re.match(rf"^(?:{_NAVEGADORES_RE})$", cand, re.IGNORECASE):
            return None
        return cand if len(cand) >= 3 else None
    return None


def titulo_para_base(titulo: str | None) -> str | None:
    """Sanitiza título do Meet para slug de arquivo (≤40, PADRAO_BASE)."""
    nome = extrair_titulo_meet(titulo)
    if not nome:
        return None
    # Normaliza acentos
    nfkd = unicodedata.normalize("NFKD", nome)
    ascii_only = nfkd.encode("ASCII", "ignore").decode("ASCII")
    # Substitui sequências não alfanum por _
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_only)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug or len(slug) < 2:
        return None
    slug = slug[:_MAX_SLUG].rstrip("_")
    # Código não deve virar slug (ex: abc-defg-hij)
    if _CODIGO_REUNIAO.match(slug.replace("_", "-")):
        return None
    return slug or None


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
    * fim: `confirma_fim` ciclos sem fonte **forte** ativa.

    O fim é deliberadamente mais lento que o início: perder o fim de uma reunião
    custa alguns segundos de áudio a mais no arquivo; cortar no meio custa a
    reunião inteira.
    """

    def __init__(
        self,
        fontes,
        confirma_inicio=CONFIRMACAO_INICIO_MEET,
        confirma_fim=CONFIRMACAO_FIM_SEM_SINAL_FORTE,
    ):
        self.fontes = list(fontes)
        self.confirma_inicio = confirma_inicio
        self.confirma_fim = confirma_fim
        self._contagem_forte = 0
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

    def titulo_reuniao_atual(self) -> str | None:
        """Retorna slug do título do Meet se houver fonte forte com nome amigável (FR-12.A1)."""
        sinais = self.ultimos_sinais or self.instantaneo()
        # Prioridade: extensão (titulo mais limpo, sem sufixo navegador) > titulo da janela
        for fonte_nome in ("extensao", "titulo"):
            for sinal in sinais:
                if sinal.forte and sinal.fonte == fonte_nome and sinal.detalhe:
                    slug = titulo_para_base(sinal.detalhe)
                    if slug:
                        return slug
        # Fallback: qualquer forte com detalhe que pareça título
        for sinal in sinais:
            if sinal.forte and sinal.detalhe:
                slug = titulo_para_base(sinal.detalhe)
                if slug:
                    return slug
        return None

    def verificar(self):
        """Um ciclo do monitor. Retorna "iniciou" | "encerrou" | None."""
        sinais = self.instantaneo()
        self.ultimos_sinais = sinais
        algum, forte, fontes_ativas = fundir(sinais)
        return self._processar(algum, forte, fontes_ativas)

    def _processar(self, algum, forte, fontes_ativas):
        if forte:
            self._contagem_fim = 0
            self._contagem_forte += 1
        else:
            self._contagem_forte = 0
            # Sinal auxiliar nunca inicia nem sustenta reunião. Antes do início,
            # não há motivo para acumular contador de fim.
            self._contagem_fim = self._contagem_fim + 1 if self._ativa else 0

        if not self._ativa:
            confirmou_forte = self._contagem_forte >= self.confirma_inicio
            if confirmou_forte:
                self._ativa = True
                self.fontes_da_reuniao = list(fontes_ativas)
                logger.info(
                    "Reunião confirmada por fonte forte: %s.",
                    ", ".join(fontes_ativas) or "?",
                )
                return "iniciou"
            return None

        if self._contagem_fim >= self.confirma_fim:
            self._ativa = False
            self.fontes_da_reuniao = []
            logger.info(
                "Reunião encerrada após %d ciclos sem sinal forte.", self._contagem_fim
            )
            return "encerrou"
        return None
