# -*- coding: utf-8 -*-
"""Testes de sincronização identificar_minha_voz com perfil.

Importa de `app_bootstrap`, onde a função mora. Importar de `transkriptor`
carregava a bandeja inteira já na coleta — e com ela o handler de log apontando
para o `transkriptor.log` de produção, antes de qualquer fixture rodar.
"""
from app_bootstrap import resolver_identificar_minha_voz as _resolver_identificar_minha_voz


def test_desativa_quando_perfil_ausente():
    cfg = {"identificar_minha_voz": True}
    ativo, cfg_out = _resolver_identificar_minha_voz(cfg, tem_perfil=False)
    assert ativo is False
    assert cfg_out["identificar_minha_voz"] is False


def test_mantem_quando_perfil_existe():
    cfg = {"identificar_minha_voz": True}
    ativo, cfg_out = _resolver_identificar_minha_voz(cfg, tem_perfil=True)
    assert ativo is True
    assert cfg_out["identificar_minha_voz"] is True


def test_default_segue_existencia_perfil():
    cfg = {}
    ativo, _ = _resolver_identificar_minha_voz(cfg, tem_perfil=True)
    assert ativo is True
    ativo, _ = _resolver_identificar_minha_voz(cfg, tem_perfil=False)
    assert ativo is False