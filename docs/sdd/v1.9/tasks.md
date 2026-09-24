# Tasks — plataforma visual e Central (SDD v1.9)

**Estado em 24/09/2026: plano aprovado; 1 `DONE` (T-14.A1), 20 `PENDING`; execução na branch `sdd-v1.9-design`, próxima task T-14.A2.** Ordem, gates e ciclo obrigatório em `plan.md`. Contratos em `interfaces.md`. Especificação visual em `design-system.md`. Prefixo de todos os IDs: `T-14`.

Os blocos **Arquivos**, **Implementação**, **RED**, **Migração de testes**, **Teste final** e **Aceite** são cumulativos. Os arquivos de teste novos são entregáveis da implementação; os seletores são planejados, não testes que já passaram. Nenhuma task usa dados reais; capturas usam `tests/e2e/fixtures/`.

## F14.A — fundação

### T-14.A1 — tokens em fonte única, temas e contraste

- [x] **Requisito:** UX-14.A1. **Depende de:** autorização e DP-14-01/02/03. **Estado:** `DONE`; commit `488e1da`; evidência: `evidencias/T-14.A1.md`.
- **Arquivos:** criar `design/tokens.json`, `scripts/gerar_tokens.py`, `design_tokens.py`, `static/css/tokens.css`, `tests/test_design_tokens.py`; modificar `estado_icone.py` (importa cores de `design_tokens`), `static/assistente.css` (passa a importar `tokens.css` e usa `--tk-*`).
- **Implementação:** JSON conforme `interfaces.md` §1; gerador com `--check`/`--write`; CSS com `:root` escuro, `@media (prefers-color-scheme: light)` e `[data-theme]`; cálculo de contraste WCAG; substituição de todos os hex do CSS atual por tokens sem mudar layout ainda (o redesenho vem em A3/B). Manter os nomes públicos `COR_*` em `estado_icone.py`.
- **RED:** `test_css_gerado_igual_ao_disco`, `test_python_gerado_igual_ao_disco`, `test_todos_pares_contraste_aa`, `test_sem_hex_fora_de_tokens_css`, `test_estado_icone_usa_design_tokens`.
- **Migração de testes:** `tests/test_v16_a_tokens.py` (`--violet`, `--gold` → verificação de `--tk-*` e ausência de `bounce`); `tests/test_v16_c_a11y.py::test_focus_visible_gold` (→ anel `--tk-accent`); `tests/test_v16_g_qualidade.py::test_detect_zero_warnings_css_js` (mantido).
- **Teste final:** `python -m pytest tests/test_design_tokens.py tests/test_v16_a_tokens.py tests/test_v16_c_a11y.py tests/test_v16_g_qualidade.py tests/test_transkiptor_estado.py -v`.
- **Aceite:** trocar um valor no JSON sem regenerar reprova `--check`; `tokens.css` claro e escuro passam contraste; página atual continua renderizando igual (captura antes/depois sem diferença de layout).

### T-14.A2 — CSP endurecida e fim do estilo inline

- [ ] **Requisito:** SEC-14.A2. **Depende de:** A1. **Estado:** `PENDING`.
- **Arquivos:** modificar `assistente.py` (CSP normativa), `templates/assistente.html` (remove `style=`, glifo "☰" e `<span>` de compatibilidade; adiciona `<link rel="icon">`), `static/assistente.css` (remove `data:` URIs em favor de sprite), `static/assistente.js` (classes `is-busy`/`is-hidden` em vez de `element.style`); criar `static/icones.svg` (mínimo: search, x, stop, send, menu), `static/favicon.ico` provisório (regenerado em E1), `tests/test_csp_front.py`, `tests/e2e/helpers.js`, `tests/e2e/csp.spec.js`.
- **Implementação:** `cabecalhos_privacidade` envia a CSP de `spec.md`; `helpers.carregarPagina` serve templates e estáticos reais via `page.route` com a CSP e coleta violações em `window.__csp`; botão Parar oculto por classe; timer oculto por classe; remoção do `☰`.
- **RED:** `csp.spec.js::carregar sem violações` (falha hoje com 5 violações); `csp.spec.js::botao parar oculto ao carregar`; `test_csp_front.py::test_html_sem_atributo_style`, `test_csp_sem_unsafe_inline`, `test_csp_mantem_frame_ancestors`.
- **Migração de testes:** `tests/test_assistente_api.py::test_html_drawer_mobile_375px` (remove exigência de "☰"; mantém `menu-toggle` e verifica `aria-label`); `tests/test_assistente_seguranca.py` continua verificando `frame-ancestors 'none'`.
- **Teste final:** `python -m pytest tests/test_csp_front.py tests/test_assistente_seguranca.py tests/test_assistente_api.py -v`; `npm run test:e2e -- csp.spec.js chat-cancel.spec.js`.
- **Aceite:** captura sob CSP idêntica à captura sem CSP; console vazio de violações; `#stop` com `display: none` ao carregar e `flex` durante geração.

### T-14.A3 — base tipográfica, ícones e componentes com galeria

- [ ] **Requisito:** UX-14.A3. **Depende de:** A2. **Estado:** `PENDING`.
- **Arquivos:** criar `static/css/base.css`, `static/css/components.css`, `templates/galeria.html`, `static/js/ui.js` (toast, dialog, panel, tema), `tests/e2e/galeria.spec.js`, `tests/e2e/fixtures/central.js`, `tests/e2e/capturar.js`; modificar `assistente.py` (rota `/galeria` só com `TRANSKRIPTOR_GALERIA=1`), `static/icones.svg` (conjunto completo), `static/assistente.css` (remove `backdrop-filter`, radiais, textura, serifa, dourado).
- **Implementação:** escala tipográfica e reset em `base.css`; componentes `tk-*` de `design-system.md` §6 com todos os estados; `ui.js` expõe `toast(tipo, titulo, texto)`, `confirmar({titulo, consequencia, perigo})` sobre `<dialog>`, `abrirPainel(id)`/`fecharPainel(id)` com foco restaurado, `aplicarTema()`; galeria renderiza cada componente em cada estado e em ambos os temas.
- **RED:** `galeria.spec.js::todos os componentes presentes em ambos os temas`, `::dialogo foca botao seguro e Esc cancela`, `::painel restaura foco`, `::toast de erro persiste e info fecha em 4s`, `::snapshot visual por componente` (baseline criada nesta task).
- **Migração de testes:** `tests/test_v16_c_a11y.py::test_drawer_860_e_375` (passa a verificar classes `tk-panel` e breakpoints de `layout.css` em B1; aqui apenas a easing `cubic-bezier(0.2, 0, 0, 1)`); `tests/test_assistente_api.py::test_html_progress_bar_durante_busy` (→ `tk-progress`).
- **Teste final:** `python -m pytest tests/test_design_tokens.py tests/test_assistente_api.py -v`; `npm run test:e2e -- galeria.spec.js csp.spec.js`.
- **Aceite:** galeria capturada em claro e escuro sem hex fora de tokens; gate visual da fase A registrado.

## F14.B — Central: assistente

### T-14.B1 — app shell, estado espelhado e tema

- [ ] **Requisito:** UX-14.B1. **Depende de:** A3 e DP-14-04/06. **Estado:** `PENDING`.
- **Arquivos:** criar `templates/base.html`, `static/css/layout.css`, `static/js/tema.js`, `static/js/estado.js`, `tests/e2e/shell.spec.js`; modificar `templates/assistente.html` (estende `base.html`), `transkriptor_menu_flows._abrir_navegador` (tenta `--app=` do Edge/Chrome; fallback `webbrowser`), `tests/test_assistente_startup.py`.
- **Implementação:** nav lateral com seis destinos e `aria-current`; barra superior com `#statusbar` alimentada por `/api/estado` (503 → "Central sem bandeja" sem erro visual); `#tema-toggle` persistido; colapso em < 1200 px, drawer em < 900 px; marca única (some do header quando a nav está visível).
- **RED:** `shell.spec.js::marca aparece uma vez em 375/900/1366/1920`, `::tema persiste apos recarregar`, `::statusbar mostra rotulo do glossario`, `::503 nao gera toast de erro`, `::Tab percorre nav → conteudo → composer`; `test_assistente_startup.py::test_abrir_navegador_prefere_janela_app_quando_disponivel` e `::test_fallback_para_webbrowser`.
- **Migração de testes:** `tests/test_v16_c_a11y.py::test_aria_labels_drawer` (IDs mantidos), `::test_drawer_860_e_375` (→ `layout.css`, 900/1200).
- **Teste final:** `python -m pytest tests/test_assistente_startup.py tests/test_v16_c_a11y.py -v`; `npm run test:e2e -- shell.spec.js csp.spec.js`.
- **Aceite:** capturas 900/1366/1920 em claro e escuro; nenhuma barra de rolagem horizontal; janela de app aberta quando o navegador suporta.

### T-14.B2 — lista de reuniões sobre o índice paginado

- [ ] **Requisito:** UX-14.B2. **Depende de:** B1. **Estado:** `PENDING`.
- **Arquivos:** criar `static/js/reunioes.js`, `templates/reunioes.html`, `tests/e2e/reunioes.spec.js`; modificar `templates/assistente.html` (`#transcricao` vira listbox), `static/js/chat.js` (extraído de `assistente.js`), `assistente.py` (`/api/transcricoes` deixa de enviar `preview` por padrão; `?preview=1` mantém o campo para compatibilidade), `tests/test_assistente_api.py`.
- **Implementação:** listbox com `role="listbox"`, `aria-activedescendant`, setas/Home/End/digitação; linhas com data, duração, badges (Protegida/Legível, Separada por vozes, Com sua voz), estado do processamento; busca preserva seleção; paginação "Carregar mais" via `/api/reunioes-indice`; estados vazio (primeiro uso com instrução), sem resultado, carregando (skeleton), erro (com "Tentar de novo"); página Reuniões reutiliza o mesmo módulo em largura total.
- **RED:** `reunioes.spec.js::lista nao mostra fala por padrao`, `::filtro preserva selecao`, `::teclado seleciona e move foco`, `::erro mostra acao e nao entra na lista`, `::carregar mais anexa sem duplicar`, `::selecionar troca contexto do chat`; `test_assistente_api.py::test_transcricoes_sem_preview_por_padrao`.
- **Migração de testes:** todos os `page.selectOption("#transcricao", …)` em `tests/e2e/*.spec.js` → helper `selecionarReuniao(page, id)`; `tests/test_assistente_api.py::test_html_copiar_resposta_e_tamanho_kb` (→ badge de tamanho); `tests/test_v16_b_assistente.py::test_js_busca_preserva_selecao` (→ E2E).
- **Teste final:** `python -m pytest tests/test_assistente_api.py tests/test_indice_transcricoes.py tests/test_v16_b_assistente.py -v`; `npm run test:e2e -- reunioes.spec.js chat-context.spec.js content-source.spec.js`.
- **Aceite:** 1.000 reuniões sintéticas listadas sem ler conteúdo; capturas dos cinco estados.

### T-14.B3 — conversa, markdown completo e chips de intenção

- [ ] **Requisito:** UX-14.B3. **Depende de:** B2. **Estado:** `PENDING`.
- **Arquivos:** criar `static/js/markdown.js`, `static/css/assistente.css` (novo, em `static/css/`), `tests/js/markdown.test.js`, `tests/e2e/chat-ui.spec.js`; modificar `static/js/chat.js`, `templates/assistente.html`, `static/assistente.js` (entrada legada importa módulos).
- **Implementação:** coluna de 72ch; mensagens como blocos (autor, hora, texto) em vez de bolhas; markdown com títulos, listas, tabelas, código, citações, links seguros; streaming renderiza markdown incremental por parágrafo fechado (sem salto final); chips de intenção com rótulo curto, `data-intent`, prompt em `static/js/intencoes.js`, botão "Ver e editar prompt" opcional; ações por mensagem (copiar, reenviar) com erro visível; empty state de primeiro uso com três passos.
- **RED:** `markdown.test.js::tabela vira table`, `::html escapado`, `::link externo tem rel noopener`; `chat-ui.spec.js::chip envia sem colar prompt no campo`, `::editar prompt mostra texto antes de enviar`, `::streaming nao altera altura ao concluir`, `::copiar negado mostra erro`.
- **Migração de testes:** `tests/test_v16_b_assistente.py::test_html_action_cards_hierarquia` (→ seis chips), `::test_html_markdown_e_copiar` (→ Vitest); `tests/test_assistente_api.py::test_html_navegacao_teclado_action_cards` (→ E2E setas nos chips); `tests/test_v16_c_a11y.py::test_keyboard_nav_cards`.
- **Teste final:** `python -m pytest tests/test_v16_b_assistente.py tests/test_assistente_api.py tests/test_v16_c_a11y.py -v`; `npm run test:unit -- tests/js/markdown.test.js`; `npm run test:e2e -- chat-ui.spec.js chat-context.spec.js chat-cancel.spec.js`.
- **Aceite:** captura de resposta com tabela renderizada; timer de 15 s preservado; largura de leitura verificada em 1920.

### T-14.B4 — estados e feedback do assistente

- [ ] **Requisito:** UX-14.B4. **Depende de:** B3. **Estado:** `PENDING`.
- **Arquivos:** modificar `static/js/chat.js`, `static/js/reunioes.js`, `static/js/ui.js`, `templates/assistente.html`; criar `tests/e2e/estados.spec.js`.
- **Implementação:** toasts tipados com título e próximo passo; skeleton na carga de lista e modelos; Ollama offline vira um cartão no lugar do composer ("Ollama não está em execução. Inicie o Ollama e clique em Tentar de novo") sem toast duplicado; transcrição longa vira aviso inline com estimativa; erro de rede vira cartão com "Tentar de novo"; nenhuma mensagem de erro dentro de `<select>`/listbox.
- **RED:** `estados.spec.js::ollama offline mostra cartao e nao toast`, `::tentar de novo recarrega modelos`, `::erro de lista nao vira item`, `::skeleton some apos carga`, `::toast de erro persiste ate fechar`.
- **Migração de testes:** `tests/test_v16_b_assistente.py::test_html_tem_search_wrap_e_header_meta` (→ contexto da reunião ativa).
- **Teste final:** `python -m pytest tests/test_v16_b_assistente.py -v`; `npm run test:e2e -- estados.spec.js reunioes.spec.js chat-ui.spec.js`.
- **Aceite:** gate da fase B; capturas de todos os estados de erro e vazio.

## F14.C — participantes e revisão

### T-14.C1 — painel de participantes

- [ ] **Requisito:** UX-14.C1. **Depende de:** B4. **Estado:** `PENDING`.
- **Arquivos:** criar `static/js/participantes.js`, `static/css/participantes.css`, `templates/participantes.html`; modificar `templates/assistente.html` (`#participantes-drawer` vira `tk-panel`), `static/assistente.js`; atualizar `tests/e2e/participants.spec.js`.
- **Implementação:** lista de falantes (nome amigável, cor estável por cluster, número de falas, tempo total, estado confirmado/sugerido/pendente, origem legenda/Meet/voz/manual); `FALANTE_00` exibido como "Falante 1" com o identificador técnico só em `title`; VOCÊ com badge; "Carregando…" substituído por skeleton e limpo após carga; versão da reunião visível como "Revisão 3".
- **RED:** `participants.spec.js::falante sem nome aparece como Falante N`, `::carregando some apos carga`, `::cores estaveis entre recargas`, `::painel empurra conteudo em 1366 e sobrepoe em 900`.
- **Migração de testes:** asserts de texto "Identificação pendente" mantidos; `#lista-participantes` continua existindo dentro do novo painel.
- **Teste final:** `python -m pytest tests/test_assistente_mutacoes.py -v`; `npm run test:e2e -- participants.spec.js accessibility.spec.js`.
- **Aceite:** captura do painel com três falantes sintéticos em claro e escuro.

### T-14.C2 — linha do tempo, sugestões e correção com undo

- [ ] **Requisito:** UX-14.C2. **Depende de:** C1. **Estado:** `PENDING`.
- **Arquivos:** modificar `static/js/participantes.js`, `static/css/participantes.css`, `templates/participantes.html`; atualizar `tests/e2e/participants.spec.js`.
- **Implementação:** segmentos em linha do tempo com tempo `[HH:MM:SS]`, falante colorido, fonte de áudio como ícone, filtro por falante; sugestão como cartão inline com origem e confiança e ações "Confirmar Ana" / "Escolher outro"; formulário de correção com seleção de falante por nome amigável e campo de nome com validação; undo com texto do que será desfeito; 409 mostra aviso inline, recarrega e mantém o painel; conteúdo sempre escapado.
- **RED:** `participants.spec.js::confirmar sugestao aplica ao cluster inteiro`, `::escolher outro foca campo e mantem cluster`, `::409 mantem painel e atualiza revisao`, `::undo mostra o que desfaz`, `::html em fala nao executa`.
- **Migração de testes:** o cenário "sugestão conserva pendência até confirmação e escapa conteúdo" é preservado com os novos seletores.
- **Teste final:** `python -m pytest tests/test_assistente_mutacoes.py tests/test_resultado_reuniao.py -v`; `npm run test:e2e -- participants.spec.js`.
- **Aceite:** fluxo confirmar → corrigir → desfazer em três capturas sequenciais.

### T-14.C3 — exportação legível e unificação com "aprender voz"

- [ ] **Requisito:** UX-14.C3. **Depende de:** C2 e DP-14-05. **Estado:** `PENDING`.
- **Arquivos:** modificar `static/js/participantes.js`, `templates/participantes.html`, `assistente.py` (`POST /api/acoes/aprender-voz`), `app_bandeja_menu.py` (item "Renomear falante" e "Corrigir nome" → abrem a Central em `/participantes`), `transkriptor_menu_flows.py` (remove `_renomear_dialog` e `iniciar_corrigir_nome_reuniao_ui`), `renomear_falante_flow.py` (remove `corrigir_nome_reuniao_ui`); criar `tests/e2e/exportar.spec.js`, `tests/test_central_api.py`.
- **Implementação:** exportação via `<dialog id="dialogo-exportar">` com consequência ("O arquivo conterá o texto legível da reunião") e botão `#confirmar-exportar`; ação separada "Aprender esta voz para próximas reuniões" com consequência explícita e opt-in, distinta de "Corrigir nome nesta reunião"; rota valida rótulo e nome e reutiliza `persistir_renomeacao_falante`.
- **RED:** `exportar.spec.js::cancelar nao chama api`, `::confirmar baixa arquivo`, `::aprender voz exige confirmacao separada`; `test_central_api.py::test_aprender_voz_sem_centroides_404`, `::test_aprender_voz_exige_header_secreto`, `::test_corrigir_nao_cadastra_biometria`.
- **Migração de testes:** `participants.spec.js` "exportação TXT exige confirmação" troca `page.once("dialog")` pelo diálogo próprio; `tests/test_renomear_falante_flow.py` mantém os testes de função pura e remove os do diálogo Tk.
- **Teste final:** `python -m pytest tests/test_central_api.py tests/test_renomear_falante_flow.py tests/test_assistente_mutacoes.py -v`; `npm run test:e2e -- exportar.spec.js participants.spec.js`.
- **Aceite:** `grep -n "simpledialog\|_renomear_dialog" *.py` sem ocorrências fora de `transkriptor_menu_flows._escolher_audio_dialog` (removido em D3); gate da fase C.

## F14.D — Central operacional

### T-14.D1 — estado ao vivo e página Início

- [ ] **Requisito:** FR-14.D1. **Depende de:** C3. **Estado:** `PENDING`.
- **Arquivos:** criar `app_estado_ui.py`, `templates/inicio.html`, `static/js/inicio.js`, `static/css/inicio.css`, `tests/test_app_estado_ui.py`, `tests/e2e/inicio.spec.js`; modificar `assistente.py` (`GET /api/estado`), `transkriptor_menu_flows.iniciar_assistente_ui` (registra provedor), `transkriptor.pyw` (nada além de expor atributos já existentes), `tests/test_lock_sem_callback.py` (cobre `app_estado_ui`).
- **Implementação:** `snapshot(app)` lê `transcritor.rodando/diarizando`, `deteccao_ativa`, `_em_erro`, `_estado_processamento`, fontes do detector e `modo_efetivo()`; última reunião via `indice_transcricoes`; nunca lê `self._lock`; página Início com três cartões e cinco últimas reuniões; polling de 2 s pausado em `document.hidden`.
- **RED:** `test_app_estado_ui.py::test_snapshot_nao_pede_lock` (AST), `::test_snapshot_sem_campos_sensiveis` (nenhuma chave fora do contrato; nenhum valor com caminho pessoal), `::test_estados_mapeiam_glossario`, `::test_503_sem_provedor`; `inicio.spec.js::polling para com aba oculta`, `::cartoes refletem estado`.
- **Migração de testes:** nenhuma.
- **Teste final:** `python -m pytest tests/test_app_estado_ui.py tests/test_lock_sem_callback.py tests/test_central_api.py -v`; `npm run test:e2e -- inicio.spec.js`.
- **Aceite:** capturas do Início nos seis estados sintéticos.

### T-14.D2 — configurações na Central e menu reduzido

- [ ] **Requisito:** FR-14.D2. **Depende de:** D1 e DP-14-08. **Estado:** `PENDING`.
- **Arquivos:** criar `templates/configuracoes.html`, `static/js/configuracoes.js`, `tests/e2e/configuracoes.spec.js`; modificar `assistente.py` (`GET/POST /api/config`), `app_bandeja_menu.py` (funções de toggle recebem `confirmar: Callable | None` e são reutilizadas pela API), `tests/test_central_api.py`, `tests/test_v16_d_bandeja.py`.
- **Implementação:** formulário agrupado (Gravação, Vozes, Google Meet, Proteção, Sistema) com consequência ao lado de cada toggle sensível; 409 com `consequencia` abre `tk-dialog` e reenvia com `confirmado`; espelhamento imediato no menu via `update_menu()`; menu reduzido conforme `interfaces.md` §5 sem remover funções.
- **RED:** `test_central_api.py::test_config_post_exige_header_secreto`, `::test_pausar_sem_confirmacao_409`, `::test_toggle_persiste_config_user`, `::test_chave_desconhecida_400`; `configuracoes.spec.js::409 abre dialogo e reenvia confirmado`; `test_v16_d_bandeja.py::test_menu_tem_no_maximo_nove_itens_de_topo`, `::test_itens_com_estado_usam_checked`.
- **Migração de testes:** `tests/test_v16_d_bandeja.py` (rótulos novos; garantir que toda função anterior continua alcançável em ≤ 2 níveis).
- **Teste final:** `python -m pytest tests/test_central_api.py tests/test_v16_d_bandeja.py tests/test_config_user_modulo.py -v`; `npm run test:e2e -- configuracoes.spec.js`.
- **Aceite:** tabela menu × Central na evidência provando paridade; captura do menu e da página.

### T-14.D3 — diagnóstico e retranscrição na Central

- [ ] **Requisito:** FR-14.D3. **Depende de:** D2 e DP-14-05. **Estado:** `PENDING`.
- **Arquivos:** criar `templates/diagnostico.html`, `static/js/diagnostico.js`, `tests/e2e/diagnostico.spec.js`; modificar `assistente.py` (`POST /api/diagnostico`, `GET /api/diagnostico/exportar`, `GET /api/audios-retidos`, `POST /api/acoes/retranscrever`), `transkriptor_menu_flows.py` (remove `_escolher_audio_dialog` e o fallback `simpledialog`; "Diagnóstico" abre a Central e mantém salvar `.txt`), `tests/test_central_api.py`, `tests/test_diagnostico.py`.
- **Implementação:** diagnóstico como lista de itens com estado (OK/Aviso/Erro), detalhe e ação sugerida por item (por exemplo "Atualizar soundcard" mostra o comando); botão "Exportar sem dados pessoais"; página de retranscrição lista áudios retidos (data, duração, nome) e inicia o job com progresso pela barra de estado; ambos funcionam sem bandeja (503 explicado).
- **RED:** `test_central_api.py::test_diagnostico_exportar_sem_pii`, `::test_retranscrever_nome_fora_da_lista_400`, `::test_retranscrever_exige_header`; `diagnostico.spec.js::itens com acao sugerida`, `::exportar baixa texto`, `::retranscrever mostra progresso`.
- **Migração de testes:** testes de `diagnostico.formatar_texto` mantidos; qualquer teste do diálogo Tk removido com registro na evidência.
- **Teste final:** `python -m pytest tests/test_central_api.py tests/test_diagnostico.py tests/test_retranscritor.py -v`; `npm run test:e2e -- diagnostico.spec.js`.
- **Aceite:** `grep -n "tkinter" *.py` sem ocorrências; gate da fase D.

## F14.E — nativos

### T-14.E1 — ícone vetorial, estados por forma e favicon

- [ ] **Requisito:** UX-14.E1. **Depende de:** D3 e DP-14-07. **Estado:** `PENDING`.
- **Arquivos:** criar `design/icone/transkriptor.svg`, `scripts/gerar_icones.py`, `static/icones/bandeja/*.png`, `tests/test_icones.py`; modificar `bandeja_icone.py`, `transkriptor.ico`, `static/favicon.ico`, `extension/meet/manifest.json` (`icons`), `extension/meet/icons/*.png`.
- **Implementação:** renderização do SVG por estado com cor do `design_tokens` e forma distinta; ICO com 16/20/24/32/48/256; variante de contorno para barra clara; `imagem_por_estado` carrega PNG e cai no desenho PIL.
- **RED:** `test_icones.py::test_ico_tem_seis_tamanhos`, `::test_estados_diferem_por_forma_nao_so_cor` (hash de máscara), `::test_cores_iguais_aos_tokens`, `::test_fallback_pil_quando_png_falta`.
- **Migração de testes:** `tests/test_transkiptor_estado.py` (cores por token).
- **Teste final:** `python -m pytest tests/test_icones.py tests/test_transkiptor_estado.py tests/test_bandeja_lifecycle.py -v`.
- **Aceite:** capturas do ícone nos seis estados sobre barra clara e escura em 100/150/200 %.

### T-14.E2 — menu da bandeja reorganizado

- [ ] **Requisito:** UX-14.E2. **Depende de:** E1. **Estado:** `PENDING`.
- **Arquivos:** modificar `app_bandeja_menu.py`, `transkriptor_acoes.py` (`texto_deteccao_menu` com glossário), `tests/test_v16_d_bandeja.py`, `docs/MANUAL-USUARIO.md` (§2).
- **Implementação:** ordem de `interfaces.md` §5; `checked=` nativo; rótulos curtos; primeira linha com o mesmo rótulo do `SnapshotEstado`; item informativo "Confirmar antes de gravar" migra para a página Configurações como texto fixo.
- **RED:** `test_v16_d_bandeja.py::test_primeira_linha_usa_glossario`, `::test_sem_prefixo_check_textual`, `::test_abrir_transkriptor_e_o_primeiro_item_acionavel`.
- **Migração de testes:** rótulos fixados em `tests/test_v16_d_bandeja.py` e `tests/test_bandeja_lifecycle.py`.
- **Teste final:** `python -m pytest tests/test_v16_d_bandeja.py tests/test_bandeja_lifecycle.py tests/test_transkiptor_estado.py -v`.
- **Aceite:** captura do menu; tabela de paridade atualizada.

### T-14.E3 — consentimento com DPI, ícone e contagem visual

- [ ] **Requisito:** UX-14.E3. **Depende de:** E2. **Estado:** `PENDING`.
- **Arquivos:** modificar `consentimento_gravacao.py` (`layout_consentimento(dpi)`, ícone, `msctls_progress32`, parâmetro `fontes`), `app_ciclo_reuniao.py` (passa fontes ativas), `config.py` (constantes de layout), `tests/test_aviso_gravacao.py`; criar `tests/test_consentimento_layout.py`.
- **Implementação:** função pura de layout escalada por DPI; título "Gravar esta reunião?"; texto com fonte detectada ("Detectado: Google Meet"); botão primário "Gravar esta reunião" e secundário "Não gravar"; barra de progresso decrescente com texto; qualquer falha nos controles novos cai no layout atual; nenhuma mudança em `pedir_consentimento`, timeouts, IDs ou `WNDPROC`.
- **RED:** `test_consentimento_layout.py::test_layout_escala_com_dpi`, `::test_botao_sim_altura_minima`, `::test_fontes_nunca_incluem_titulo_ou_nome`; `test_aviso_gravacao.py` inalterado e verde.
- **Migração de testes:** nenhuma; `tests/test_portao_consentimento.py` é regressão obrigatória.
- **Teste final:** `python -m pytest tests/test_consentimento_layout.py tests/test_aviso_gravacao.py tests/test_portao_consentimento.py tests/test_lock_sem_callback.py -v`.
- **Aceite:** capturas do diálogo em 100/150/200 % (ensaio local com `--sem-audio` não conta como gate de captura); evidência registra que o fail-closed não mudou.

### T-14.E4 — confirmações padronizadas

- [ ] **Requisito:** UX-14.E4. **Depende de:** E3. **Estado:** `PENDING`.
- **Arquivos:** criar `confirmacoes.py` (textos de consequência únicos), `tests/test_confirmacoes.py`; modificar `app_bandeja_menu.py`, `assistente.py` (`consequencia` de `/api/config` vem de `confirmacoes`), `static/js/configuracoes.js`.
- **Implementação:** um dicionário `CONSEQUENCIAS` por ação (pausar, sair gravando, modo protegido, apagar perfil, exportar legível) usado pelo `MessageBoxW` da bandeja e pelo diálogo da Central; `MessageBoxW` mantém título, ícone de aviso e botão padrão seguro.
- **RED:** `test_confirmacoes.py::test_todas_as_acoes_tem_consequencia`, `::test_central_e_bandeja_usam_o_mesmo_texto`, `::test_botao_padrao_e_seguro`.
- **Migração de testes:** asserts de texto em `tests/test_v16_d_bandeja.py` apontam para `confirmacoes`.
- **Teste final:** `python -m pytest tests/test_confirmacoes.py tests/test_v16_d_bandeja.py tests/test_central_api.py -v`.
- **Aceite:** captura de uma confirmação na bandeja e da mesma na Central.

### T-14.E5 — pareamento da extensão com a mesma identidade

- [ ] **Requisito:** UX-14.E5. **Depende de:** E4. **Estado:** `PENDING`.
- **Arquivos:** modificar `extension/meet/pairing.html`, `extension/meet/pairing.js`, `extension/meet/README.md`, `scripts/gerar_tokens.py` (`--extensao`); criar `extension/meet/pairing.css`, `tests/js/pairing-ui.test.js`; atualizar `tests/e2e/meet-transport.spec.js`.
- **Implementação:** passos numerados (abrir Diagnóstico → copiar código → colar → parear), campo com validação de prefixo, estados carregando/sucesso/erro com ícone, marca e tema pelo `prefers-color-scheme`; nenhuma requisição além do WebSocket local.
- **RED:** `pairing-ui.test.js::sucesso mostra estado e desabilita campo`, `::erro mostra proximo passo`; `test_design_tokens.py::test_pairing_css_gerado_igual`.
- **Migração de testes:** IDs `#codigo`, `#parear`, `#estado` mantidos.
- **Teste final:** `python -m pytest tests/test_design_tokens.py -v`; `npm run test:unit -- tests/js/pairing-ui.test.js`; `npm run test:e2e -- meet-transport.spec.js`.
- **Aceite:** captura da página nos três estados; gate da fase E.

## F14.F — acessibilidade e orçamento

### T-14.F1 — gate de acessibilidade comportamental

- [ ] **Requisito:** NFR-14.F1. **Depende de:** E5 e DP-14-09. **Estado:** `PENDING`.
- **Arquivos:** modificar `package.json`/lock (`@axe-core/playwright`), `tests/e2e/accessibility.spec.js`; criar `tests/e2e/axe.spec.js`, `tests/e2e/larguras.spec.js`, `docs/sdd/v1.9/evidencias/roteiro-narrador.md`.
- **Implementação:** axe em todas as páginas e na galeria, ambos os temas, sem violações `serious`/`critical`; percurso de teclado completo por página; `forced-colors` e `reduced-motion` emulados; 375/900/1366/1920 sem overflow e sem texto cortado; roteiro manual de Narrador executado e registrado.
- **RED:** `axe.spec.js::sem violacoes serias em cada pagina e tema`, `larguras.spec.js::sem overflow`, `accessibility.spec.js::foco visivel em todos os controles`.
- **Migração de testes:** `tests/test_v16_c_a11y.py` reduzido a `forced-colors`/`reduced-motion` presentes; o resto vira E2E.
- **Teste final:** `python -m pytest tests/test_v16_c_a11y.py tests/test_design_tokens.py -v`; `npm run test:e2e -- axe.spec.js larguras.spec.js accessibility.spec.js`.
- **Aceite:** relatório axe anexado; roteiro de Narrador com data e resultado.

### T-14.F2 — orçamento de front e zero rede

- [ ] **Requisito:** NFR-14.F2. **Depende de:** F1. **Estado:** `PENDING`.
- **Arquivos:** criar `tests/test_orcamento_front.py`; modificar `static/assistente.css` e `static/assistente.js` (removidos se nenhum teste legado restar; caso contrário mantidos como entradas mínimas), `tests/e2e/csp.spec.js` (todas as páginas).
- **Implementação:** teste soma bytes de `static/css`, `static/js`, sprite e ICO; E2E garante zero requisições fora de `127.0.0.1` em todas as páginas; medição local de primeira renderização registrada na evidência.
- **RED:** `test_orcamento_front.py::test_css_ate_80kb`, `::test_js_ate_150kb`, `::test_sprite_ate_40kb`; `csp.spec.js::nenhuma requisicao externa em todas as paginas`.
- **Migração de testes:** `tests/front_assistente.py` e testes que concatenam HTML+CSS+JS atualizados para os arquivos finais.
- **Teste final:** `python -m pytest tests/test_orcamento_front.py tests/test_csp_front.py tests/test_assistente_api.py -v`; `npm run test:e2e -- csp.spec.js`.
- **Aceite:** gate da fase F.

## F14.G — fechamento

### T-14.G1 — manual, glossário, evidências e decisão de versão

- [ ] **Requisito:** NFR-14.G1. **Depende de:** F2 e DP-14-11. **Estado:** `PENDING`.
- **Arquivos:** modificar `docs/MANUAL-USUARIO.md` (capturas sintéticas de todas as superfícies, §2 e §7 reescritos, glossário), `scripts/gerar_manual_pdf.py` se existir, `docs/sdd/v1.9/README.md` (estado final), `docs/sdd/README.md`, `AGENTS.md` (tabela de versões); criar `docs/sdd/v1.9/evidencias/GATE-FINAL.md`, `tests/test_manual_v19.py`.
- **Implementação:** manual com uma captura por superfície e por tema; glossário de `design-system.md` §9; gate final de `plan.md` executado; decisão DP-14-11 registrada sem alterar `config.VERSAO` nesta task.
- **RED:** `test_manual_v19.py::test_manual_referencia_todas_as_superficies`, `::test_capturas_existem_e_sao_sinteticas` (nomes das fixtures presentes, nenhum nome real).
- **Migração de testes:** `tests/test_manual_usuario.py` atualizado.
- **Teste final:** `python -m pytest tests/test_manual_v19.py tests/test_manual_usuario.py tests/test_sdd_rastreabilidade.py -v`; `python scripts/verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v1.9`.
- **Aceite:** gate G verde; `GATE-FINAL.md` com SHA, comandos, resultados e lista de capturas.
