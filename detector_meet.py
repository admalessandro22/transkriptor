# -*- coding: utf-8 -*-
"""Reconhecimento de reunião pelo título da janela, com debounce.

O Google Meet mudou o formato do título da aba: hoje ele é
`Meet – abc-defg-hij` (travessão), e não mais `<sala> - Google Meet`.
Este módulo aceita **os dois** formatos, além do link `meet.google.com/<codigo>`
e das reuniões do Zoom, para que nenhuma reunião real passe despercebida.

Duas classes de casamento (FR-9.2):

* **forte** — código de reunião presente (`abc-defg-hij`) ou título que começa
  com `Meet –`. Não passa pela lista de exclusão: uma sala pode se chamar
  "Ajuda ao cliente" e nem por isso deixa de ser uma reunião.
* **nomeado** — formato legado `<sala> - Google Meet`. Passa pela exclusão para
  descartar resultados de busca, tutoriais e páginas de ajuda.
"""

import logging
import re

from config import CONFIRMACAO_INICIO_MEET, CONFIRMACAO_FIM_MEET

logger = logging.getLogger(__name__)

# Código de sala do Meet: 3 letras - 4 letras - 3 letras (ex.: abc-defg-hij).
_CODIGO = r"[a-z]{3,4}-[a-z]{3,4}-[a-z]{3,4}"

# Casamento forte: não sofre exclusão por palavra-chave.
_PADRAO_FORTE = re.compile(
    # "Meet – abc-defg-hij", "Meet - abc-defg-hij" (título atual do Meet)
    rf"(?:(?:^|[|\-–—]\s)Meet\s*[-–—]\s*{_CODIGO}\b)"
    # título começa com "Meet – <qualquer coisa>" (sala com nome do Calendar)
    rf"|(?:^Meet\s*[-–—]\s+\S)"
    # link colado no título / barra de endereços
    rf"|(?:meet\.google\.com/{_CODIGO})"
    # formato legado com código: "abc-defg-hij - Google Meet"
    rf"|(?:{_CODIGO}\s*[-–—]\s*Google\s*Meet\b)",
    re.IGNORECASE,
)

# Casamento nomeado (legado): "<sala> - Google Meet [- Navegador]"
_PADRAO_NOMEADO = re.compile(
    r".+\s-\sGoogle\sMeet(?=$|\s[-—–]\s)",
    re.IGNORECASE,
)

# Reunião do Zoom: a janela em chamada se chama "Zoom Meeting"/"Reunião Zoom".
# A janela ociosa do app ("Zoom Workplace") de propósito não casa.
_PADRAO_ZOOM = re.compile(
    r"\bZoom\s+(?:Meeting|Webinar|Reuni[aã]o)\b|\bReuni[aã]o\s+do\s+Zoom\b",
    re.IGNORECASE,
)

# Palavras que indicam que NÃO é uma reunião ativa (buscas, tutoriais, ajuda).
_EXCLUIR = re.compile(
    r"(pesquisa|search|como\s+(?:usar|configurar)|tutorial|ajuda|help|"
    r"sign\s?in|login|account|novidades)",
    re.IGNORECASE,
)


def classificar_titulo(titulo):
    """Retorna "forte", "nomeado" ou "" para o título recebido.

    Exposta para o diagnóstico da bandeja: permite mostrar ao usuário por que
    uma janela foi (ou não foi) considerada reunião.
    """
    if not titulo or not str(titulo).strip():
        return ""
    texto = str(titulo).strip()
    if _PADRAO_FORTE.search(texto) or _PADRAO_ZOOM.search(texto):
        return "forte"
    if _PADRAO_NOMEADO.search(texto) and not _EXCLUIR.search(texto):
        return "nomeado"
    return ""


def titulo_eh_meet(titulo, *, visivel=True, exigir_janela_visivel=False):
    """Retorna True apenas se o título parece uma reunião ativa."""
    if exigir_janela_visivel and not visivel:
        return False
    return bool(classificar_titulo(titulo))


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
