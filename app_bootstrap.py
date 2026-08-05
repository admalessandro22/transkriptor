# -*- coding: utf-8 -*-
"""Leitura/gravação da config na subida do app (parte do bootstrap, FR-8.2).

Fica fora de `transkriptor.pyw` só para manter aquele arquivo dentro do limite
de 500 linhas. Os nomes continuam sendo importados para o namespace do `.pyw`,
onde os testes os substituem.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def carregar_config_user():
    import config_user

    return config_user.carregar()


def salvar_config_user(cfg):
    import config_user

    try:
        config_user.salvar(cfg)
    except Exception as e:  # noqa: BLE001 — config ruim não pode derrubar a subida
        logging.error(f"Erro ao salvar config_user: {e}")


def resolver_identificar_minha_voz(cfg, tem_perfil):
    """Só identifica `VOCÊ` se houver perfil cadastrado; senão desliga a flag."""
    ativo = cfg.get("identificar_minha_voz", tem_perfil) and tem_perfil
    if cfg.get("identificar_minha_voz") and not tem_perfil:
        cfg["identificar_minha_voz"] = False
    return ativo, cfg
