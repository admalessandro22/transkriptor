# Plano de Remediação — Auditoria v1.2

## P0

Nenhum achado P0 aberto após baseline verde.

## P1 — Executado

| Achado | Ação | Arquivos | Teste |
|--------|------|----------|-------|
| A-01 Token query | `token_requisicao_valido()` no Flask | `assistente.py` | `test_api_com_token_query_param_retorna_200` |
| A-02 .gitignore | Ignorar `_modelo_voz/`, `config_user.json` | `.gitignore` | `test_git_check_ignore_caminhos_sensiveis` |
| A-03 Payload WS | Limite 4 KB em `processar_mensagem` | `meet_bridge.py`, `config.py` | `test_processar_mensagem_rejeita_payload_grande` |
| A-04 Sanitizar nome | `sanitizar_nome_participante()` | `meet_bridge.py` | `test_sanitizar_nome_remove_controle_e_trunca` |

## P2 — Adiado (justificativa)

| Achado | Decisão | Motivo |
|--------|---------|--------|
| A-05 Criptografia `.tkpt` | v1.3 | Escopo grande (DPAPI, migração); não bloqueia uso local atual |
| A-06 Badge VOCÊ assistente | Backlog | FR-7.11 P3 opcional |
| A-07 UIA Meet | Backlog | FR-8.6 P3; extensão Chrome cobre fluxo principal |
| A-08 Numeração fases | Docs only | `PLANO-FINAL.md` é fonte canônica |
| A-09 Cobertura watchdog | Backlog | Gates funcionais cobrem regressões críticas |

## Critérios de done

- [x] Todo P1 corrigido ou testado
- [x] `pytest tests/` verde 2×
- [x] `verificar_fase.py --fase all` verde 2×
- [x] Manual MD + PDF publicados