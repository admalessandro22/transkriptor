# Transkriptor: plataforma visual e Central — Implementation Plan (SDD v1.9)

**Goal:** dar ao Transkriptor uma única identidade visual moderna, sóbria e tecnológica em todas as superfícies, e uma Central local que concentre estado, reuniões, assistente, revisão, configurações e diagnóstico, sem alterar captura, contratos de dados ou garantias de privacidade da v1.8.

**Architecture:** tokens em fonte única (`design/tokens.json`) gerando CSS e Python; Flask existente ampliado com rotas aditivas e páginas novas; módulos ES sem bundler; bandeja como lançador e indicador; consentimento Win32 redesenhado no lugar. Detalhes em `concept.md`, `design-system.md` e `interfaces.md`.

**Tech Stack:** o mesmo da v1.8 (Python 3.12+, Flask, pystray, ctypes/Win32, Playwright, Vitest, pytest) mais `@axe-core/playwright` como devDependency (DP-14-09). Nenhuma biblioteca de UI, framework ou CDN.

## Restrições globais

Valem integralmente os invariantes de `spec.md` e as decisões DU-01–DU-16 da v1.8. Plano **aprovado em 24/09/2026** com as recomendações padrão de `decisoes-usuario.md`; execução autorizada a partir de T-14.A1 na branch `sdd-v1.9-design` (DP-14-12 revisada), isolada da branch de remediação v1.8. Sem bump, push, release, instalação real ou gate físico sem autorização própria.

Estados de task: `PENDING`, `IN_PROGRESS`, `BLOCKED`, `DONE`. `DONE` exige requisito, RED comportamental, GREEN, teste final, regressão, evidência com capturas sintéticas e commit local no mesmo `HEAD`.

## Ordem de implantação

| Fase | Objetivo | Saída que libera a próxima |
|---|---|---|
| F14.A | Fundação: tokens e temas, CSP endurecida sem inline, componentes e galeria | Página atual servida sob a CSP real sem violação; galeria com todos os componentes |
| F14.B | Central: shell, lista de reuniões, conversa, estados | Assistente redesenhado consumindo o índice paginado, E2E verdes sob CSP |
| F14.C | Participantes e revisão: painel, linha do tempo, exportação, unificação com renomear | Fluxo completo de revisão sem identificadores técnicos; Tk de nome removidos |
| F14.D | Central operacional: Início com estado ao vivo, Configurações, Diagnóstico e retranscrição | Bandeja deixa de ser a única interface; Tk restantes removidos |
| F14.E | Nativos: ícone, menu, consentimento, confirmações, extensão | Identidade única do ícone ao pareamento |
| F14.F | Gates de acessibilidade e orçamento | axe, teclado, larguras, tamanho e zero rede como testes |
| F14.G | Fechamento: manual, glossário, evidências, decisão de versão | Release candidata documentada; bump é decisão separada |

Dependências: A1 → A2 → A3 → B1 → B2 → B3 → B4 → C1 → C2 → C3 → D1 → D2 → D3 → E1 → E2 → E3 → E4 → E5 → F1 → F2 → G1. E1–E5 não dependem de C/D funcionalmente, mas ficam depois para que o vocabulário de estados da Central esteja fixado antes de tocar o nativo. Não executar tasks em paralelo.

## Ciclo obrigatório de cada task

- [ ] Ler requisito, contratos (`interfaces.md`), especificação visual (`design-system.md`) e casos negativos da task.
- [ ] Escrever o teste de comportamento descrito em `tasks.md`; rodar e confirmar RED pelo comportamento (não por import ausente).
- [ ] Implementar a menor alteração coesa nos arquivos definidos. Migrar na mesma task os testes legados de substring listados; nunca apagar cobertura comportamental.
- [ ] Rodar o teste final e a regressão da task; ambos GREEN. Rodar `python scripts/gerar_tokens.py --check` sempre que CSS mudar.
- [ ] Gerar capturas sintéticas (`node tests/e2e/capturar.js <task>`) e revisar visualmente contra `design-system.md`: contraste, espaçamento, estados, texto do glossário.
- [ ] Registrar comando, data, ambiente, exit code, resultado e lista de testes migrados em `evidencias/T-14.Xn.md`, sem dados pessoais.
- [ ] Commit em português, imperativo, só com arquivos da task. Ex.: `feat: gera tokens de design em fonte única`.

Se um teste falhar: investigar a causa, corrigir e repetir o mesmo gate. Não ajustar o esperado para esconder o defeito. A última task da fase roda também o gate da fase.

## Gates por fase

Os seletores abaixo passam a existir com as respectivas tasks; não são evidência atual.

| Fase | Gate automatizado | Evidência adicional |
|---|---|---|
| A | `python -m pytest tests/test_design_tokens.py tests/test_csp_front.py tests/test_assistente_seguranca.py tests/test_v16_g_qualidade.py -v`; `npm run test:e2e -- csp.spec.js galeria.spec.js` | Capturas da galeria em claro e escuro; console sem violação de CSP |
| B | `python -m pytest tests/test_assistente_api.py tests/test_indice_transcricoes.py -v`; `npm run test:e2e -- shell.spec.js reunioes.spec.js chat-context.spec.js chat-cancel.spec.js content-source.spec.js` | Capturas 900/1366/1920 do Assistente com dados sintéticos; tabela markdown renderizada |
| C | `python -m pytest tests/test_assistente_mutacoes.py tests/test_renomear_falante_flow.py -v`; `npm run test:e2e -- participants.spec.js exportar.spec.js` | Fluxo confirmar → corrigir → desfazer → exportar em captura; `grep` prova ausência dos diálogos Tk removidos |
| D | `python -m pytest tests/test_app_estado_ui.py tests/test_central_api.py tests/test_lock_sem_callback.py tests/test_diagnostico.py -v`; `npm run test:e2e -- inicio.spec.js configuracoes.spec.js diagnostico.spec.js` | Snapshot sem campos sensíveis (teste negativo); toggles espelhados entre menu e Central |
| E | `python -m pytest tests/test_icones.py tests/test_v16_d_bandeja.py tests/test_portao_consentimento.py tests/test_aviso_gravacao.py tests/test_transkiptor_estado.py -v`; `npm run test:unit` | Capturas do ícone em barra clara/escura 100/150/200 %; consentimento em 3 escalas; pareamento |
| F | `python -m pytest tests/test_orcamento_front.py tests/test_design_tokens.py -v`; `npm run test:e2e -- accessibility.spec.js axe.spec.js larguras.spec.js` | Roteiro de Narrador executado e registrado; relatório axe anexado |
| G | `python -m pytest tests/ -q --tb=short`; `python scripts/verificar_fase.py --fase all`; `python scripts/verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v1.9`; `npm ci`; `npm run test:unit`; `npm run test:e2e`; `python -m pip check`; `git diff --check` | Manual com todas as capturas; decisão DP-14-11 registrada |

## Gate visual (manual, por fase)

Antes de fechar cada fase, revisar as capturas sintéticas contra esta lista e registrar na evidência:

1. Nenhum hex, tamanho ou duração fora dos tokens (teste) e nenhum componente fora da galeria (revisão).
2. Todos os estados de cada componente presentes: vazio, carregando, erro, sucesso, desabilitado, foco.
3. Texto do glossário: nenhum `FALANTE_XX` sem nome amigável, nenhum ".tkpt"/"diarizado" como badge, nenhum "Erro: …" sem próximo passo.
4. Tema claro e escuro; `forced-colors`; 375/900/1366/1920 sem overflow.
5. Foco visível em todos os controles por Tab; Esc fecha painéis e diálogos; foco restaurado.
6. Nenhum dado real em captura; fixtures de `tests/e2e/fixtures/`.

## Migração e rollback

- Rotas e formatos existentes não mudam; rotas novas são aditivas e desligáveis por ausência de provedor (`/api/estado` responde 503 sem quebrar a página).
- Itens de menu migrados para a Central só saem do menu na task que entrega a página equivalente verde; a mesma task remove o diálogo Tk correspondente. Reverter é `git revert` da task.
- `static/assistente.css` e `static/assistente.js` permanecem como entradas até os testes legados migrarem; a remoção final é parte de F14.F2.
- Ícone: `bandeja_icone.py` cai no desenho PIL se os PNGs faltarem; o `.ico` antigo é regenerado a partir da fonte vetorial, não editado à mão.
- Consentimento: qualquer falha na criação de controles novos (ícone, barra de progresso) cai para o layout atual; o comportamento fail-closed não depende de nenhum recurso novo.
- Nenhuma task toca `transcricao_core.py`, `captura_leve.py`, `fila_processamento.py`, `processador_reuniao.py`, `crypto_*`, `politica_privacidade.py`, `identidade_reuniao.py` nem `resultado_*.py`.

## Estimativa de esforço

Faixas para planejamento, não promessa, uma pessoa incluindo testes e revisão: A 3–5 dias úteis; B 6–9; C 4–6; D 6–10; E 5–8; F 3–5; G 2–3. Total 29–46 dias úteis. Reestimar após A3 (fundação) e B2 (primeira página completa).

## Critério de entrega

A–G `DONE`, gates verdes no mesmo commit, evidências com capturas sintéticas de todas as superfícies, manual atualizado, `verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v1.9` OK, e decisão de versão registrada (DP-14-11). Commit/push/publicação só no fluxo autorizado; a presente solicitação entrega diagnóstico e plano.
