# -*- coding: utf-8 -*-
"""Estado observado da extensão do Meet: idioma e saúde do canal (T-15.B1/B4).

Só códigos e números chegam aqui (já validados em `sessao_reuniao`). O
Diagnóstico usa a última saúde para dizer o motivo provável quando os nomes
não chegam — sem texto de fala, nome nem bytes de pacote.
"""
from __future__ import annotations

from typing import Mapping

CAMPOS_IDIOMA = ("caption_lang", "lang_requested")
CAMPOS_SAUDE = ("raw", "parsed", "rejected", "recriacoes", "quedas", "motivos", "esqueleto", "build_meet", "tactiq")


def registrar_estado_meet(bridge, evento: Mapping) -> None:
    if evento.get("kind") == "capabilities":
        bridge.idiomas_meet = {k: evento[k] for k in CAMPOS_IDIOMA if k in evento}
    elif evento.get("kind") == "health":
        bridge.saude_meet = {k: evento[k] for k in CAMPOS_SAUDE if k in evento}
