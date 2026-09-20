# -*- coding: utf-8 -*-
"""Inventário e recuperação segura de sessão (T-13.E2)."""
from __future__ import annotations

import json
import logging
import os
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, Mapping, Sequence

from artefatos import sha256_arquivo
from config import (
    RECUPERACAO_REGISTRO,
    RECUPERACAO_RESTRITO,
    RECUPERACAO_SESSOES,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecoveryItem:
    relative_path: str
    owner_session_id: str | None
    state: str
    action: str


def _raiz_resolvida(root: Path) -> Path:
    return Path(root).resolve()


def _dir_sessao(root: Path, session_id: str) -> Path:
    return Path(root) / RECUPERACAO_SESSOES / str(session_id)


def _relativo_seguro(caminho: Path, raiz: Path) -> str | None:
    try:
        resolvido = caminho.resolve()
    except OSError:
        return None
    try:
        return resolvido.relative_to(raiz).as_posix()
    except ValueError:
        return None


def _escrever_json_atomico(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(
        prefix=f"{caminho.stem}_", suffix=".tmp", dir=str(caminho.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, sort_keys=True)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        try:
            if os.path.isfile(temporario):
                os.remove(temporario)
        except OSError:
            pass


def _identidade_processo() -> dict:
    from fila_lock import current_process_identity

    ident = current_process_identity()
    return {"pid": ident.pid, "created_at_100ns": ident.created_at_100ns}


def registrar_inicio(root: Path, session_id: str, *, estado: str = "gravando") -> Path:
    """Abre o diretório privado da sessão com lease do escritor atual."""
    pasta = _dir_sessao(Path(root), session_id)
    (pasta / "audio").mkdir(parents=True, exist_ok=True)
    _escrever_json_atomico(
        pasta / RECUPERACAO_REGISTRO,
        {
            "session_id": str(session_id),
            "lease": {
                "owner": _identidade_processo(),
                "nonce": secrets.token_hex(8),
            },
            "arquivos_ativos": [],
            "estado": str(estado),
        },
    )
    return pasta


def _carregar_registro(pasta_sessao: Path) -> dict | None:
    caminho = pasta_sessao / RECUPERACAO_REGISTRO
    if not caminho.is_file():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def registrar_ativo(root: Path, session_id: str, caminho: str) -> None:
    """Anota um arquivo ativo da sessão (relativo à raiz; fora dela é erro)."""
    raiz = _raiz_resolvida(Path(root))
    pasta = _dir_sessao(raiz, session_id)
    if not pasta.is_dir():
        registrar_inicio(raiz, session_id)
    relativo = _relativo_seguro(Path(caminho), raiz)
    if relativo is None:
        raise ValueError("arquivo ativo fora da raiz da sessão")
    registro = _carregar_registro(pasta) or {}
    ativos = list(registro.get("arquivos_ativos") or [])
    if relativo not in ativos:
        ativos.append(relativo)
    registro["arquivos_ativos"] = ativos
    _escrever_json_atomico(pasta / RECUPERACAO_REGISTRO, registro)


def finalizar_sessao(root: Path, session_id: str, *, estado: str = "concluida") -> None:
    pasta = _dir_sessao(Path(root), session_id)
    registro = _carregar_registro(pasta) or {"session_id": str(session_id)}
    registro["estado"] = str(estado)
    registro["arquivos_ativos"] = []
    _escrever_json_atomico(pasta / RECUPERACAO_REGISTRO, registro)


def tem_escritor_vivo(registro: Mapping) -> bool:
    """Lease com dono vivo bloqueia ação destrutiva; dúvida também bloqueia."""
    try:
        from fila_lock import ProcessIdentity, process_matches

        dono = (registro or {}).get("owner") or {}
        ident = ProcessIdentity(
            pid=int(dono["pid"]), created_at_100ns=int(dono["created_at_100ns"])
        )
        return bool(process_matches(ident))
    except Exception:  # noqa: BLE001 — indeterminado = trata como vivo
        return True


def _eh_link_externo(caminho: Path, raiz: Path) -> bool:
    if caminho.is_symlink():
        return True
    try:
        if os.path.isjunction(str(caminho)):
            return True
    except (AttributeError, OSError, ValueError):
        pass
    return _relativo_seguro(caminho, raiz) is None


def _padrao_legado(relativo: str) -> str | None:
    """Órfãos de áreas de trabalho — NUNCA de `audio/` ou `sessoes/` assentados.

    `audio/` é o lar de gravações concluídas (pós-move do stop); tocá-lo sem
    posse provada moveu dados reais em 2026-09-20. Só registro de sessão
    (dono) ou áreas de trabalho justificam ação automática.
    """
    if relativo.startswith("audio/") or relativo.startswith(f"{RECUPERACAO_SESSOES}/"):
        return None
    base = relativo.rsplit("/", 1)[-1].lower()
    if base.startswith("diarizacao_"):
        return "diarizacao"
    if base.endswith((".tmp", "_audio.wav", "_mic.wav", "_audio.wav.enc", "_mic.wav.enc")):
        return "audio-trabalho"
    return None


def inventariar(root: Path, live_sessions: Collection[str]) -> tuple[RecoveryItem, ...]:
    """Varre SÓ a raiz (nunca o TEMP global); nada é movido ou removido aqui."""
    raiz = _raiz_resolvida(Path(root))
    if not raiz.is_dir():
        return ()
    vivas = set(live_sessions or ())
    registros: dict[str, dict] = {}
    base_sessoes = raiz / RECUPERACAO_SESSOES
    if base_sessoes.is_dir():
        for pasta in sorted(base_sessoes.iterdir()):
            if pasta.is_dir() and not pasta.is_symlink():
                reg = _carregar_registro(pasta)
                if reg is not None:
                    registros[pasta.name] = reg
    ativos_por_arquivo: dict[str, str] = {}
    concluidas: set[str] = set()
    for sid, reg in registros.items():
        if sid in vivas:
            continue
        if str(reg.get("estado", "")) == "concluida":
            concluidas.add(sid)
            continue
        for rel in reg.get("arquivos_ativos") or []:
            ativos_por_arquivo.setdefault(str(rel), sid)
    itens: list[RecoveryItem] = []
    vistos: set[str] = set()
    for atual, dirs, arquivos in os.walk(raiz, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not Path(atual, d).is_symlink())
        for nome in sorted(arquivos):
            caminho = Path(atual) / nome
            if caminho.name in (RECUPERACAO_REGISTRO, "indice.json"):
                continue
            if caminho.is_symlink() or _eh_link_externo(caminho, raiz):
                itens.append(RecoveryItem(caminho.name, None, "externo", "recusar_externo"))
                continue
            relativo = _relativo_seguro(caminho, raiz)
            if relativo is None:
                continue
            if relativo in vistos:
                continue
            vistos.add(relativo)
            dono = None
            partes = relativo.split("/")
            if len(partes) >= 3 and partes[0] == RECUPERACAO_SESSOES:
                dono = partes[1]
            if dono is not None and dono in concluidas:
                continue  # sessão encerrada: arquivos assentados, nada a fazer
            if dono is not None and dono in vivas:
                itens.append(RecoveryItem(relativo, dono, "viva", "preservar_viva"))
                continue
            if dono is not None:
                itens.append(RecoveryItem(relativo, dono, "para_recuperar", "recuperar_mover"))
                continue
            if relativo in ativos_por_arquivo:
                itens.append(
                    RecoveryItem(relativo, ativos_por_arquivo[relativo], "para_recuperar", "recuperar_mover")
                )
                continue
            if _padrao_legado(relativo) is not None:
                if relativo.lower().endswith(".wav") and (raiz / (relativo + ".enc")).is_file():
                    itens.append(RecoveryItem(relativo, None, "para_consolidar", "consolidar_cifra"))
                elif relativo.lower().endswith(".wav.enc"):
                    base = relativo[: -len(".enc")]
                    if (raiz / base).is_file() and _padrao_legado(base) is not None:
                        continue  # cópia validada sai com o .wav na consolidação
                    itens.append(RecoveryItem(relativo, None, "para_recuperar", "recuperar_mover"))
                else:
                    itens.append(RecoveryItem(relativo, None, "para_recuperar", "recuperar_mover"))
                continue
            itens.append(RecoveryItem(relativo, None, "desconhecido", "sinalizar"))
    return tuple(itens)


def _destino_recuperado(raiz: Path, item: RecoveryItem) -> Path:
    nome = Path(item.relative_path).name
    if item.owner_session_id:
        return raiz / RECUPERACAO_SESSOES / item.owner_session_id / "audio" / nome
    return raiz / RECUPERACAO_SESSOES / "recuperado-legado" / nome


def _consolidar_cifra(raiz: Path, caminho_wav: Path) -> RecoveryItem | None:
    """Par .wav + .wav.enc: remove o plaintext SÓ após equivalência validada."""
    from crypto_storage import ler_bytes_arquivo

    enc = caminho_wav.with_name(caminho_wav.name + ".enc")
    if not enc.is_file():
        return None
    try:
        plano = ler_bytes_arquivo(str(enc))
    except Exception:  # noqa: BLE001 — cifra ilegível: preserva tudo
        return RecoveryItem(
            caminho_wav.name, None, "sinalizado", "sinalizar"
        )
    try:
        if hashlib_sha(plano) != sha256_arquivo(caminho_wav):
            return RecoveryItem(caminho_wav.name, None, "sinalizado", "sinalizar")
        caminho_wav.unlink()
        return RecoveryItem(caminho_wav.name, None, "consolidado", "consolidar_cifra")
    except OSError:
        return RecoveryItem(caminho_wav.name, None, "aguardando_escritor", "aguardar_escritor")


def hashlib_sha(dados: bytes) -> str:
    import hashlib

    return hashlib.sha256(dados).hexdigest()


def registrar_wavs_abertos(transcritor) -> None:
    """Anota os WAVs recém-abertos na sessão; nunca quebra a captura."""
    try:
        vinculo = getattr(transcritor, "_recuperacao", None)
        if vinculo is None:
            return
        raiz, sid = vinculo
        registrar_ativo(raiz, sid, transcritor._caminho_wav)
        if getattr(transcritor, "_caminho_wav_mic", None):
            registrar_ativo(raiz, sid, transcritor._caminho_wav_mic)
    except Exception:  # noqa: BLE001
        logger.debug("Registro de recuperação indisponível", exc_info=True)


def selar_transcritor(transcritor, caminho) -> None:
    """Sela a sessão ao fim do stop íntegro; pendência mantém o registro."""
    try:
        vinculo = getattr(transcritor, "_recuperacao", None)
        if vinculo is not None and caminho is not None:
            finalizar_sessao(vinculo[0], vinculo[1])
    except Exception:  # noqa: BLE001
        logger.debug("Selo de recuperação indisponível", exc_info=True)


def sob_recuperacao_ativa(caminho: str | Path) -> bool:
    """True se o arquivo pertence a sessão não concluída (retenção não toca)."""
    try:
        atual = Path(caminho).resolve(strict=True)
    except OSError:
        return False
    for pai in atual.parents:
        try:
            if pai.parent.name != RECUPERACAO_SESSOES:
                continue
            registro = _carregar_registro(pai)
        except OSError:
            continue
        if registro is None:
            continue
        return str(registro.get("estado", "")) != "concluida"
    return False


def recuperar(
    root: Path, items: Sequence[RecoveryItem], *, dry_run: bool = True
) -> tuple[RecoveryItem, ...]:
    """Executa ações seguras; dry_run (padrão) só planeja. Nunca remove a única cópia."""
    raiz = _raiz_resolvida(Path(root))
    saidas: list[RecoveryItem] = []
    for item in items:
        if dry_run or item.action in (
            "preservar_viva",
            "sinalizar",
            "recusar_externo",
            "aguardar_escritor",
        ):
            saidas.append(item)
            continue
        try:
            origem = (raiz / item.relative_path).resolve()
        except OSError:
            saidas.append(item)
            continue
        if not origem.is_file() or _relativo_seguro(origem, raiz) is None:
            saidas.append(
                RecoveryItem(item.relative_path, item.owner_session_id, "recusado", "recusar_externo")
            )
            continue
        if item.action == "recuperar_mover":
            destino = _destino_recuperado(raiz, item)
            try:
                destino.parent.mkdir(parents=True, exist_ok=True)
                antes = sha256_arquivo(origem)
                destino_temp = destino
                indice = 2
                while destino_temp.exists():
                    destino_temp = destino.with_name(f"{destino.stem}_{indice:02d}{destino.suffix}")
                    indice += 1
                origem.replace(destino_temp)
                if sha256_arquivo(destino_temp) != antes:
                    raise OSError("hash divergente após mover")
                saidas.append(
                    RecoveryItem(item.relative_path, item.owner_session_id, "recuperado", item.action)
                )
            except OSError:
                saidas.append(
                    RecoveryItem(item.relative_path, item.owner_session_id, "aguardando_escritor", "aguardar_escritor")
                )
            continue
        if item.action == "consolidar_cifra":
            feito = _consolidar_cifra(raiz, origem)
            saidas.append(feito if feito is not None else item)
            continue
        saidas.append(item)
    return tuple(saidas)
