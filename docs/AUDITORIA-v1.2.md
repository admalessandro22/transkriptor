# Auditoria v1.2 — Qualidade, Segurança e Coerência

**Data:** 2026-07-09  
**Escopo:** Transkriptor v1.2 (bandeja, transcrição, diarização, VOCÊ, Meet, assistente)  
**Baseline:** 108 testes pytest verdes; gate `verificar_fase.py --fase all` OK

---

## 1. Metodologia

- Cruzamento `docs/sdd/v1.2/spec.md` (FR/SEC/NFR) ↔ código ↔ `tests/`
- Revisão de superfícies locais: Flask `127.0.0.1`, WebSocket Meet, paths, logs, tokens
- Classificação: **P0** bloqueia release · **P1** corrige nesta auditoria · **P2** adiado documentado

---

## 2. Achados

| ID | Severidade | Área | Achado | Requisito |
|----|------------|------|--------|-----------|
| A-01 | P1 | Segurança | API `/api/*` aceitava token só no header; `?token=` da spec não validado no servidor | FR-6.1, SEC-4 |
| A-02 | P1 | Segurança | `.gitignore` não cobria `vozes_conhecidas.json` nem `config_user.json` | FR-9.1, SEC-7 |
| A-03 | P1 | Segurança | Meet bridge sem limite de payload WebSocket (risco DoS local) | SEC-6 |
| A-04 | P1 | Segurança | Nomes de participantes sem sanitização (chars de controle / nomes enormes) | SEC-6 |
| A-05 | P2 | Coerência | Criptografia em repouso (`.tkpt`, DPAPI) não implementada | FR-3.1–3.8 |
| A-06 | P2 | Coerência | Badge "com sua voz" no assistente ausente | FR-7.11 |
| A-07 | P2 | Coerência | Fallback UI Automation Meet não implementado | FR-8.6 |
| A-08 | P2 | Coerência | Numeração de fases diverge entre `spec.md` (F3=crypto) e `tasks.md` (F3=UX bandeja) | Documentação |
| A-09 | P2 | Qualidade | Cobertura 70% em `watchdog.py` não medida formalmente | NFR-1 |

---

## 3. Pontos fortes

- Path traversal bloqueado (`caminho_transcricao_seguro`) com testes
- Anti-XSS no select do assistente (`buildSelectOptions`)
- Flask restrito a `127.0.0.1`; token `secrets.token_urlsafe(32)`
- Mutex de instância única; log com rotação
- Gates SDD F0–F8 automatizados (108 testes)
- Prioridade Meet > voz conhecida > VOCÊ validada em testes

---

## 4. Status pós-remediação

| ID | Status |
|----|--------|
| A-01 | **Corrigido** — `token_requisicao_valido()` |
| A-02 | **Corrigido** — `.gitignore` ampliado |
| A-03 | **Corrigido** — `MAX_MENSAGEM_MEET_WS` |
| A-04 | **Corrigido** — `sanitizar_nome_participante()` |
| A-05 | **Adiado** — escopo P2; ver PLANO-REMEDIACAO |
| A-06 | **Adiado** — P3 opcional |
| A-07 | **Adiado** — P3 opcional |
| A-08 | **Documentado** — usar `PLANO-FINAL.md` como canônico |
| A-09 | **Adiado** — métrica futura |

---

## 5. Conclusão

O produto está **coerente e seguro para uso local** nas superfícies auditadas. Achados P1 foram corrigidos com testes. Itens P2 permanecem no backlog v1.3 (criptografia, badge, UIA Meet).