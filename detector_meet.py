# -*- coding: utf-8 -*-
"""Detecção robusta de Google Meet com debounce.

Regex específico evita falso-positivos (buscas, páginas de ajuda).
Debounce de N ciclos consecutivos evita oscilação start/stop quando
o título da aba pisca durante o carregamento.
"""

import logging
import re

from config import CONFIRMACAO_INICIO_MEET, CONFIRMACAO_FIM_MEET

logger = logging.getLogger(__name__)

# Título do Meet ativo: "<nome da sala> - Google Meet"
# Também aceita "meet.google.com/<codigo>" enquanto carrega.
_PADRAO_MEET = re.compile(
    r"(?:.+\s-\sGoogle\sMeet(?=$|\s[-—]\s))"
    r"|(?:meet\.google\.com/[a-z0-9]+(?:-[a-z0-9]+)+)",
    re.IGNORECASE,
)

# Palavras que indicam que NÃO é uma reunião ativa (buscas, tutoriais, ajuda)
_EXCLUIR = re.compile(
    r"(pesquisa|search|como\s+(?:usar|configurar)|tutorial|ajuda|help|"
    r"sign\s?in|login|account|novidades)",
    re.IGNORECASE,
)


def titulo_eh_meet(titulo, *, visivel=True, exigir_janela_visivel=False):
    """Retorna True apenas se o título parece uma reunião ativa do Meet."""
    if exigir_janela_visivel and not visivel:
        return False
    if not titulo or not titulo.strip():
        return False
    if _EXCLUIR.search(titulo):
        return False
    return bool(_PADRAO_MEET.search(titulo.strip()))


class DetectorMeet:
    """Detector com debounce: confirma início/fim após N ciclos consecutivos.

    Uso:
        detector = DetectorMeet()
        # a cada INTERVALO_MONITOR_MEET segundos:
        estado = detector.verificar(titulos das janelas)
        # estado: "iniciou" | "encerrou" | None
    """

    def __init__(
        self,
        confirma_inicio=CONFIRMACAO_INICIO_MEET,
        confirma_fim=CONFIRMACAO_FIM_MEET,
        exigir_janela_visivel=False,
    ):
        self.confirma_inicio = confirma_inicio
        self.confirma_fim = confirma_fim
        self.exigir_janela_visivel = exigir_janela_visivel
        self._contagem_inicio = 0
        self._contagem_fim = 0
        self._meet_ativo = False

    @property
    def meet_ativo(self):
        return self._meet_ativo

    def verificar_janelas(self, janelas):
        """Processa janelas com metadados {titulo, visivel} e retorna mudança de estado."""
        return self._processar(
            any(
                titulo_eh_meet(
                    j.get("titulo", ""),
                    visivel=j.get("visivel", True),
                    exigir_janela_visivel=self.exigir_janela_visivel,
                )
                for j in janelas
            )
        )

    def verificar(self, titulos):
        """Processa a lista de títulos de janelas e retorna mudança de estado.

        Retorna:
            "iniciou"  — o Meet acabou de ser confirmado (antes não tinha, agora tem)
            "encerrou" — o Meet acabou de ser encerrado (antes tinha, agora não)
            None       — sem mudança de estado
        """
        tem_meet = any(
            titulo_eh_meet(t, exigir_janela_visivel=self.exigir_janela_visivel)
            for t in titulos
        )
        return self._processar(tem_meet)

    def _processar(self, tem_meet):

        if tem_meet:
            self._contagem_inicio += 1
            self._contagem_fim = 0
        else:
            self._contagem_fim += 1
            self._contagem_inicio = 0

        if not self._meet_ativo and self._contagem_inicio >= self.confirma_inicio:
            self._meet_ativo = True
            logger.info("Meet confirmado após %d detecções.", self._contagem_inicio)
            return "iniciou"

        if self._meet_ativo and self._contagem_fim >= self.confirma_fim:
            self._meet_ativo = False
            logger.info("Meet encerrado após %d ausências.", self._contagem_fim)
            return "encerrou"

        return None
