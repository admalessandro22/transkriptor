# -*- coding: utf-8 -*-
"""Resumo curto (≤ 500 caracteres) de cada reunião com a IA local (Ollama).

Pedido do usuário (24/09/2026): o resumo aparece ao passar o mouse no nome da
reunião. Regras:
- o resumo é conteúdo: fica cifrado em `transcricoes/resumos/` (AES-GCM do
  `crypto_storage`), nunca no índice e nunca no log;
- uma reunião por vez, em segundo plano, e nunca enquanto a bandeja grava ou
  processa (não disputa CPU/GPU com a captura nem com o Whisper);
- a revisão do resultado entra no arquivo: corrigir um nome refaz o resumo.
"""
from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

LIMITE = 500
MODELOS_PREFERIDOS = ("gemma4", "gemma3", "qwen2.5", "llama3.1", "granite4.1")
_PADRAO_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_PROMPT = (
    "Você resume reuniões em português do Brasil. Responda só com o resumo, em no "
    "máximo 500 caracteres, em texto corrido (sem títulos, listas ou markdown): o "
    "assunto principal, as decisões e quem ficou responsável pelo quê. Use os nomes "
    "que aparecem na transcrição; não invente fatos."
)


class ResumoIndisponivel(RuntimeError):
    """Sem conteúdo para resumir ou IA local fora do ar; nunca vira resumo."""


# ---- texto e limite --------------------------------------------------------

def _nome_do_falante(seg: dict, mapeamento: dict, ordem: list[str]) -> str:
    cluster = str(seg.get("speaker_cluster_id", ""))
    manual = mapeamento.get(cluster)
    if isinstance(manual, dict) and manual.get("display_name"):
        return str(manual["display_name"])
    atrib = seg.get("assignment") if isinstance(seg.get("assignment"), dict) else {}
    if atrib.get("status") == "confirmed" and atrib.get("display_name"):
        return str(atrib["display_name"])
    return f"Falante {ordem.index(cluster) + 1}" if cluster in ordem else "Falante"


def texto_da_reuniao(dados: dict) -> str:
    """Uma linha por fala: `[mm:ss] Nome: texto` (hh:mm:ss acima de 1 h)."""
    segmentos = [s for s in (dados or {}).get("segmentos") or [] if isinstance(s, dict)]
    mapeamento = (dados or {}).get("mapeamento") or {}
    mapeamento = mapeamento if isinstance(mapeamento, dict) else {}
    ordem = sorted({str(s.get("speaker_cluster_id", "")) for s in segmentos})
    linhas = []
    for seg in segmentos:
        texto = str(seg.get("text") or "").strip()
        if not texto:
            continue
        seg_total = max(0, int(seg.get("start_ms") or 0) // 1000)
        h, m, s = seg_total // 3600, (seg_total % 3600) // 60, seg_total % 60
        hora = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        linhas.append(f"[{hora}] {_nome_do_falante(seg, mapeamento, ordem)}: {texto}")
    return "\n".join(linhas)


def limitar_resumo(texto: str, limite: int = LIMITE) -> str:
    """Espaços normalizados; acima do limite corta na última frase inteira."""
    limpo = re.sub(r"\s+", " ", str(texto or "")).strip().strip('"').strip()
    limpo = re.sub(r"^(resumo|summary)\s*:\s*", "", limpo, flags=re.IGNORECASE)
    if len(limpo) <= limite:
        return limpo
    corte = limpo[:limite]
    fim_frase = max(corte.rfind(". "), corte.rfind("! "), corte.rfind("? "))
    if corte.endswith((".", "!", "?")):
        return corte
    if fim_frase >= limite // 3:
        return corte[: fim_frase + 1]
    return corte[: limite - 1].rsplit(" ", 1)[0].rstrip(",;: ") + "…"


def escolher_modelo(instalados: list[str]) -> str | None:
    for preferido in MODELOS_PREFERIDOS:
        for nome in instalados:
            if nome.split(":")[0] == preferido:
                return nome
    return instalados[0] if instalados else None


def gerar_resumo(
    dados: dict,
    modelo: str,
    chamar: Callable[[str, list[dict]], str],
    *,
    orcamento_chars: int,
) -> str:
    texto = texto_da_reuniao(dados)
    if not texto:
        raise ResumoIndisponivel("reunião sem falas")
    pedido = "Resuma esta reunião em até 500 caracteres."
    if len(texto) <= orcamento_chars:
        mensagens = [{"role": "system", "content": _PROMPT},
                     {"role": "user", "content": f"{pedido}\n\nTranscrição:\n{texto}"}]
        resposta = chamar(modelo, mensagens)
    else:
        from resumo_longo import dividir_em_blocos, responder_longo

        def chamar_com_prompt(m: str, msgs: list[dict]) -> str:
            return chamar(m, [{"role": "system", "content": _PROMPT}, *msgs])

        resposta = responder_longo(
            modelo, dividir_em_blocos(texto, orcamento_chars), pedido,
            chamar_com_prompt, orcamento_chars=orcamento_chars,
        )
    if not resposta or resposta.startswith("[Erro"):
        raise ResumoIndisponivel("IA local indisponível")
    resumo = limitar_resumo(resposta)
    if not resumo:
        raise ResumoIndisponivel("IA local devolveu resumo vazio")
    return resumo


# ---- serviço em segundo plano ---------------------------------------------

class ServicoResumos:
    """Fila única de geração; estado por reunião: gerando | pronto | indisponivel."""

    def __init__(
        self,
        pasta: Path,
        *,
        carregar: Callable[[str], dict | None],
        chamar: Callable[[str, list[dict]], str],
        modelos: Callable[[], list[str]],
        ocupado: Callable[[], bool] = lambda: False,
        orcamento: Callable[[str], int] = lambda modelo: 12000,
        espera_ocupado_seg: float = 30.0,
    ) -> None:
        self.pasta = Path(pasta)
        self._carregar = carregar
        self._chamar = chamar
        self._modelos = modelos
        self._ocupado = ocupado
        self._orcamento = orcamento
        self._espera = float(espera_ocupado_seg)
        self._lock = threading.Lock()
        self._pendentes: set[str] = set()
        self._falhas: dict[str, str] = {}
        self._fila: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()

    # -- disco (sempre cifrado) --
    def _arquivo(self, meeting_id: str) -> Path:
        return self.pasta / f"{meeting_id}.resumo"

    def _ler(self, meeting_id: str) -> dict | None:
        caminho = self._arquivo(meeting_id)
        if not caminho.is_file():
            return None
        try:
            from crypto_storage import ler_bytes_arquivo

            dados = json.loads(ler_bytes_arquivo(str(caminho)).decode("utf-8"))
            return dados if isinstance(dados, dict) and isinstance(dados.get("resumo"), str) else None
        except Exception:  # noqa: BLE001 — arquivo ilegível: refaz
            return None

    def _gravar(self, meeting_id: str, revisao: str, resumo: str, modelo: str) -> None:
        from crypto_storage import salvar_bytes_arquivo

        corpo = json.dumps({"revision": revisao, "resumo": resumo, "modelo": modelo}, ensure_ascii=False)
        salvar_bytes_arquivo(str(self._arquivo(meeting_id)), corpo.encode("utf-8"))

    # -- API --
    def obter(self, meeting_id: str) -> dict:
        if not _PADRAO_ID.fullmatch(str(meeting_id)):
            return {"estado": "indisponivel", "motivo": "reunião inválida"}
        dados = self._carregar(meeting_id)
        if not dados:
            return {"estado": "indisponivel", "motivo": "reunião sem resultado"}
        salvo = self._ler(meeting_id)
        if salvo and salvo.get("revision") == dados.get("revision"):
            return {"estado": "pronto", "resumo": salvo["resumo"]}
        with self._lock:
            motivo = self._falhas.get(meeting_id)
            if motivo is not None:
                return {"estado": "indisponivel", "motivo": motivo}
            if meeting_id not in self._pendentes:
                self._pendentes.add(meeting_id)
                self._fila.put(meeting_id)
                self._garantir_thread()
        return {"estado": "gerando"}

    def tentar_de_novo(self, meeting_id: str) -> None:
        with self._lock:
            self._falhas.pop(meeting_id, None)

    def parar(self) -> None:
        self._parar.set()
        self._fila.put(None)

    # -- trabalho --
    def _garantir_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._parar.clear()
            self._thread = threading.Thread(target=self._laco, name="resumos-reuniao", daemon=True)
            self._thread.start()

    def _laco(self) -> None:
        while not self._parar.is_set():
            meeting_id = self._fila.get()
            if meeting_id is None:
                return
            while self._ocupado() and not self._parar.is_set():
                time.sleep(self._espera)
            try:
                self._processar(meeting_id)
            finally:
                with self._lock:
                    self._pendentes.discard(meeting_id)

    def _processar(self, meeting_id: str) -> None:
        try:
            dados = self._carregar(meeting_id)
            if not dados:
                raise ResumoIndisponivel("reunião sem resultado")
            modelo = escolher_modelo(list(self._modelos() or []))
            if modelo is None:
                raise ResumoIndisponivel("IA local sem modelo instalado")
            resumo = gerar_resumo(dados, modelo, self._chamar, orcamento_chars=self._orcamento(modelo))
            if not self._carregar(meeting_id):
                return  # excluída enquanto o resumo era gerado: não recria dado
            self._gravar(meeting_id, str(dados.get("revision", "")), resumo, modelo)
        except ResumoIndisponivel as exc:
            motivo = str(exc)
            with self._lock:
                self._falhas[meeting_id] = motivo
            logger.info("Resumo de reunião não gerado: %s.", motivo)
        except Exception:  # noqa: BLE001 — nunca derruba a Central
            with self._lock:
                self._falhas[meeting_id] = "IA local indisponível"
            logger.info("Resumo de reunião não gerado: falha inesperada.", exc_info=True)
