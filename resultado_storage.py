# -*- coding: utf-8 -*-
"""Persistência confinada do resultado canônico, aberta ou cifrada."""
from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Mapping

from artefatos import ArtifactRef, criar_referencia, referencia_integra
from crypto_storage import ler_bytes_arquivo, salvar_bytes_arquivo
from politica_privacidade import ProtectionMode
from resultado_edicao import _escrever_json_atomico, validar_dados_segmentos

FORMATO_ABERTO = "application/vnd.transkriptor.segments+json"
FORMATO_CIFRADO = "application/vnd.transkriptor.segments+json+encrypted"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")


def _escrever_cifrado_atomico(caminho: Path, cifrado: bytes) -> None:
    fd, temporario = tempfile.mkstemp(prefix=f"{caminho.stem}_", suffix=".tmp", dir=caminho.parent)
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(cifrado)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
        temporario = None
    finally:
        if temporario:
            Path(temporario).unlink(missing_ok=True)


class ResultadoStorage:
    def __init__(self, raiz: Path, modo: ProtectionMode):
        self.raiz = Path(raiz).resolve()
        self.modo = ProtectionMode(modo)

    def caminho(self, meeting_id: str) -> Path:
        if not _ID.fullmatch(str(meeting_id)) or meeting_id in (".", ".."):
            raise ValueError("identificador de reunião inválido")
        extensao = ".json.enc" if self.modo == ProtectionMode.PROTECTED else ".json"
        return self.raiz / "resultados" / f"{meeting_id}{extensao}"

    @contextmanager
    def _lock(self, meeting_id: str):
        alvo = self.caminho(meeting_id)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with (alvo.parent / f".{meeting_id}.lock").open("a+b") as arquivo:
            arquivo.seek(0)
            if os.name == "nt":
                import msvcrt

                if arquivo.seek(0, os.SEEK_END) == 0:
                    arquivo.write(b"\0")
                    arquivo.flush()
                arquivo.seek(0)
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                arquivo.seek(0)
                if os.name == "nt":
                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)

    def _journal(self, meeting_id: str) -> Path:
        self.caminho(meeting_id)  # valida o identificador antes de formar paths
        return self.raiz / "resultados" / f".{meeting_id}.rollback"

    def _limpar_journal(self, meeting_id: str) -> None:
        journal = self._journal(meeting_id)
        for nome in ("meta.json", "manifest.bin", "segments.bin", "export.bin"):
            (journal / nome).unlink(missing_ok=True)
        journal.rmdir()

    def _criar_journal(self, meeting_id: str, caminho_manifesto: Path,
                       caminho_json: Path, caminho_txt: Path) -> None:
        journal = self._journal(meeting_id)
        journal.mkdir(exist_ok=False)
        try:
            arquivos = {"manifest.bin": caminho_manifesto, "segments.bin": caminho_json,
                        "export.bin": caminho_txt}
            meta = {}
            for nome, alvo in arquivos.items():
                plano = alvo.read_bytes()  # backups cifrados; manifesto só tem metadados
                _escrever_cifrado_atomico(journal / nome, plano)
                meta[nome] = {"path": alvo.relative_to(self.raiz).as_posix(),
                              "sha256": hashlib.sha256(plano).hexdigest()}
            _escrever_cifrado_atomico(
                journal / "meta.json", json.dumps(meta, sort_keys=True).encode("utf-8")
            )
        except Exception:
            self._limpar_journal(meeting_id)
            raise

    def _recuperar_journal(self, meeting_id: str) -> None:
        from resultado_reuniao import validar_manifesto

        journal = self._journal(meeting_id)
        if not journal.exists():
            return
        if not (journal / "meta.json").exists():
            from resultado_reuniao import carregar_manifesto

            for caminho in self.raiz.glob("*.resultado.json"):
                try:
                    if (carregar_manifesto(caminho).meeting_id == meeting_id
                            and validar_manifesto(caminho, self.raiz)):
                        self._limpar_journal(meeting_id)
                        return
                except (OSError, ValueError):
                    continue
            raise ValueError("journal incompleto sem resultado íntegro")
        meta = json.loads((journal / "meta.json").read_text(encoding="utf-8"))
        alvos = {}
        for nome in ("manifest.bin", "segments.bin", "export.bin"):
            entrada = meta[nome]
            caminho = (self.raiz / entrada["path"]).resolve()
            if not caminho.is_relative_to(self.raiz) or not caminho.is_file():
                raise ValueError("journal de edição inválido")
            if hashlib.sha256((journal / nome).read_bytes()).hexdigest() != entrada["sha256"]:
                raise ValueError("journal de edição adulterado")
            alvos[nome] = caminho
        if validar_manifesto(alvos["manifest.bin"], self.raiz):
            self._limpar_journal(meeting_id)
            return
        for nome in ("segments.bin", "export.bin", "manifest.bin"):
            _escrever_cifrado_atomico(alvos[nome], (journal / nome).read_bytes())
        if not validar_manifesto(alvos["manifest.bin"], self.raiz):
            raise ValueError("recuperação da edição inválida")
        self._limpar_journal(meeting_id)

    def save(self, meeting_id: str, payload: Mapping[str, object]) -> ArtifactRef:
        destino = self.caminho(meeting_id)
        destino.parent.mkdir(parents=True, exist_ok=True)
        dados = dict(payload)
        if self.modo == ProtectionMode.PROTECTED:
            plano = (json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            salvar_bytes_arquivo(str(destino), plano)
            formato = FORMATO_CIFRADO
        else:
            _escrever_json_atomico(destino, dados)
            formato = FORMATO_ABERTO
        return criar_referencia(destino, self.raiz, format=formato, schema_version=1)

    def load(self, ref: ArtifactRef) -> dict[str, object]:
        if ref.format not in (FORMATO_ABERTO, FORMATO_CIFRADO):
            raise ValueError("formato de resultado inválido")
        if not referencia_integra(ref, self.raiz):
            raise ValueError("referência de resultado inválida")
        caminho = self.raiz / ref.relative_path
        plano = (ler_bytes_arquivo(str(caminho)) if ref.format == FORMATO_CIFRADO
                 else caminho.read_bytes())
        return validar_dados_segmentos(json.loads(plano.decode("utf-8")))

    def manifesto(self, meeting_id: str):
        """Resolve reunião pelo manifesto, sem inferir nome de arquivo a partir da URL."""
        with self._lock(meeting_id):
            return self._manifesto_sem_lock(meeting_id)

    def _manifesto_sem_lock(self, meeting_id: str):
        from resultado_reuniao import carregar_manifesto, validar_manifesto

        if not _ID.fullmatch(str(meeting_id)) or meeting_id in (".", ".."):
            raise ValueError("identificador de reunião inválido")
        self._recuperar_journal(meeting_id)
        encontrados = []
        for caminho in self.raiz.glob("*.resultado.json"):
            try:
                manifesto = carregar_manifesto(caminho)
                if manifesto.meeting_id == meeting_id and validar_manifesto(caminho, self.raiz):
                    encontrados.append((caminho, manifesto))
            except (OSError, ValueError):
                continue
        if len(encontrados) != 1:
            raise ValueError("reunião não encontrada ou manifesto inválido")
        return encontrados[0]

    def editar(self, meeting_id: str, *, acao: str, expected_revision: str,
              speaker_cluster_id: str = "", display_name: str = "") -> str:
        """Edita canônico cifrado e seu TXT derivado, sem temporário aberto."""
        with self._lock(meeting_id):
            return self._editar_sem_lock(meeting_id, acao=acao,
                                         expected_revision=expected_revision,
                                         speaker_cluster_id=speaker_cluster_id,
                                         display_name=display_name)

    def _editar_sem_lock(self, meeting_id: str, *, acao: str, expected_revision: str,
                        speaker_cluster_id: str, display_name: str) -> str:
        from artefatos import criar_referencia
        from crypto_storage import salvar_transcricao
        from resultado_edicao import corrigir_payload, desfazer_payload, exportar_txt
        from resultado_reuniao import salvar_manifesto

        caminho_manifesto, manifesto = self._manifesto_sem_lock(meeting_id)
        if manifesto.segments_ref.format != FORMATO_CIFRADO:
            raise ValueError("resultado não usa armazenamento protegido")
        dados = self.load(manifesto.segments_ref)
        if acao == "corrigir":
            revisao = corrigir_payload(dados, expected_revision=expected_revision,
                                      speaker_cluster_id=speaker_cluster_id,
                                      participant_id=None, display_name=display_name)
        elif acao == "desfazer":
            revisao = desfazer_payload(dados, expected_revision=expected_revision)
        else:
            raise ValueError("ação inválida")
        refs_txt = [ref for ref in manifesto.exports if ref.format == "application/vnd.transkriptor.tkpt"]
        if len(refs_txt) != 1 or not referencia_integra(refs_txt[0], self.raiz):
            raise ValueError("exportação inválida")
        caminho_txt = self.raiz / refs_txt[0].relative_path
        caminho_json = self.raiz / manifesto.segments_ref.relative_path
        texto = exportar_txt(dados["segmentos"], dados.get("mapeamento", {}))
        self._criar_journal(meeting_id, caminho_manifesto, caminho_json, caminho_txt)
        try:
            novo_json = self.save(meeting_id, dados)
            salvar_transcricao(str(caminho_txt), texto)
            novo_txt = criar_referencia(caminho_txt, self.raiz,
                                       format=refs_txt[0].format, schema_version=1)
            exports = tuple(novo_txt if ref == refs_txt[0] else ref for ref in manifesto.exports)
            salvar_manifesto(caminho_manifesto,
                             replace(manifesto, segments_ref=novo_json, exports=exports))
            self._limpar_journal(meeting_id)
        except Exception:
            self._recuperar_journal(meeting_id)
            raise
        return revisao
