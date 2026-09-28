# Diagnóstico UI/UX — Transkriptor (base 1.7.0, código em 24/09/2026)

Base examinada: `5566f074011948457571cf934c8fb02c8855a6e8`, produto `config.VERSAO = 1.7.0`.
Método: inspeção de todo o código de interface, renderização real do assistente com Playwright em 375/860/1366 px (dados sintéticos) e carga da página sob a CSP de produção. Capturas e scripts em `evidencias/diagnostico/`. Nenhuma transcrição, áudio ou configuração real foi aberta.

Este documento diagnostica; não certifica. A avaliação heurística é opinião de design fundamentada em evidência verificável; onde há defeito reproduzível, o item diz como reproduzir.

## 1. Inventário de superfícies

O produto não tem uma "tela principal". A experiência está espalhada por onze superfícies produzidas por quatro tecnologias diferentes, sem nenhum ativo visual compartilhado entre elas.

| # | Superfície | Tecnologia | Arquivo | Estilo atual |
|---|---|---|---|---|
| S1 | Ícone da bandeja e tooltip | PIL desenhado em runtime | `bandeja_icone.py`, `estado_icone.py` | Círculo colorido + microfone branco, 64 px |
| S2 | Menu da bandeja | pystray (menu nativo Win32) | `app_bandeja_menu.py` | 24 itens, 4 submenus, prefixo textual "✓ " |
| S3 | Diálogo de consentimento | Win32 puro via ctypes | `consentimento_gravacao.py` | Janela cinza padrão, 520×272 px fixos |
| S4 | Confirmações (pausar, sair, modo protegido) | `MessageBoxW` | `app_bandeja_menu.py` | Caixa de mensagem do sistema |
| S5 | Notificações | Balão do pystray | `notificador.py` | Silenciosas por padrão (correto) |
| S6 | Retranscrever áudio, Renomear falante | Tkinter/ttk tema "vista" | `transkriptor_menu_flows.py` | Claro, Segoe UI 8–11 pt, cinzas hardcoded |
| S7 | Corrigir nome da reunião | `filedialog` + 2× `simpledialog` | `renomear_falante_flow.py` | Diálogos genéricos do Tk |
| S8 | Relatório de diagnóstico | `.txt` aberto no Bloco de Notas | `diagnostico.py` | Texto monoespaçado |
| S9 | Assistente web (sidebar, chat, composer, drawer de participantes) | Flask + HTML/CSS/JS | `templates/assistente.html`, `static/*` | Escuro, violeta + dourado + serifa |
| S10 | Pareamento da extensão | HTML na extensão | `extension/meet/pairing.html` | `font-family: sans-serif`, sem estilo |
| S11 | Primeira execução | `.bat` + atalho | `instalar.bat`, `iniciar_bandeja.bat` | Console; sem boas-vindas |

Conclusão do inventário: a peça mais elaborada (S9) representa uma fração do uso; os momentos decisivos do produto (S3 consentimento, S1/S2 estado, S8 "por que não gravou?") são os menos cuidados.

## 2. Achados

Severidade: **Crítico** (quebra visível em produção ou bloqueia a percepção de qualidade), **Alto** (mina a confiança ou a eficiência), **Médio** (polimento com impacto real), **Baixo** (higiene).

### Críticos

**D01 — A CSP de produção quebra a interface do assistente.** `assistente.py` envia `Content-Security-Policy: default-src 'self'`. Sem `style-src`, os atributos `style="display:none"` do template são bloqueados; sem `img-src`, os `data:` URIs do CSS também. Resultado em produção: o botão vermelho **Parar** aparece permanentemente ao lado de **Enviar**, o `<div class="timer">` fica visível, o glifo "☰" de compatibilidade aparece ao lado do ícone de menu, o ícone de limpar busca some e a textura de fundo não carrega. Reproduzível com `evidencias/diagnostico/csp.js`; captura `08-csp-producao.png`; console do navegador registra cinco violações. Os testes E2E não pegam isso porque usam `page.setContent()` sem cabeçalhos. Causa raiz: estilo inline no HTML combinado com CSP sem diretivas explícitas.

**D02 — O drawer de participantes não tem design.** `#participantes-drawer` recebe apenas `overflow-x: hidden` no CSS. Renderiza como texto cru sobre o chat: título sem margem, botões nativos cinza do sistema, campo de texto sem estilo, rótulos técnicos expostos ao usuário ("Identificação pendente (pendente, incerto)"), sem agrupamento por falante, sem cor por falante, sem separação entre lista, formulário e ações. Em 375 px o texto encosta na borda esquerda. Capturas `03`, `06`, `07`. Defeito funcional adicional: `carregarResultado()` escreve "Carregando..." em `#participantes-estado` e nunca limpa após sucesso, então a mensagem fica presa até a próxima ação.

**D03 — Não existe identidade visual; existem cinco.** O assistente é escuro com dourado, serifa Georgia e violeta ("premium"). Os diálogos Tk são claros com tema "vista". O consentimento é uma janela cinza padrão. O pareamento da extensão não tem estilo. O ícone é um círculo azul-escuro desenhado por código. Não há símbolo, paleta, tipografia ou tom de voz compartilhados. Para o usuário, são cinco programas diferentes com o mesmo nome.

### Altos

**D04 — A bandeja é a única "home" e está sobrecarregada.** O menu tem 24 itens e 4 submenus. Rótulos misturam ação, estado e suporte: "Diagnóstico (por que não está gravando?)", "Modo legendas Meet (Tactiq)", "Ativar modo protegido para novas reuniões…", "Abrir pasta vozes conhecidas". O estado é indicado por prefixo textual "✓ " em vez do `checked` nativo do pystray. Um item desabilitado é usado como texto informativo ("✓ Confirmar antes de gravar (obrigatório)"). Não há hierarquia entre a ação principal (abrir o assistente) e configurações raras (startup, modelo Whisper).

**D05 — A lista de reuniões é um `<select>` com strings concatenadas.** Cada opção vira `22/09/2026 10:03 — Bom dia a todos, va… [vozes] · com sua voz`, truncada pelo controle nativo. Não há hierarquia, estados de carregamento, ordenação ou filtros. O `preview` expõe a primeira frase da reunião na lista por padrão, algo que a própria spec v1.8 (UX-13.F3) já pede para eliminar. O endpoint paginado `/api/reunioes-indice` existe, mas o front continua lendo `/api/transcricoes` e carregando tudo.

**D06 — Fluxos irmãos com três interfaces diferentes.** "Corrigir nome nesta reunião" pede ao usuário escolher um `.json` no explorador e digitar `FALANTE_00` de memória em dois `simpledialog`. "Renomear falante" abre um diálogo Tk próprio. "Participantes" no assistente faz a mesma correção em HTML. O usuário precisa aprender três caminhos para uma tarefa.

**D07 — O consentimento, momento mais importante do produto, parece um diálogo de instalador.** Janela Win32 sem ícone, botões do sistema, rótulo "●  Sim, gravar reunião" com bullet Unicode, dimensões fixas em pixels sem tratar DPI, contagem regressiva textual, sem dizer qual reunião ou fonte foi detectada. As garantias fail-closed estão corretas e devem ser preservadas; a forma não transmite a seriedade da decisão.

**D08 — O diagnóstico entrega um `.txt` no Bloco de Notas.** Quebra a experiência, não é acionável (sem link para corrigir) e não tem a marca do produto. O conteúdo é bom; o veículo não.

**D09 — Contraste abaixo de AA nos textos secundários.** Calculado sobre os tokens atuais: `--text-4 #5e5953` sobre `--panel-solid #12121a` ≈ 2,7:1; `--text-3 #807a73` ≈ 4,4:1. Ambos são usados em texto de 10–11 px (rótulos de campo, contadores, atalhos, "Copiar" sob cada resposta, rodapé). O mínimo para texto normal é 4,5:1.

**D10 — Ações rápidas injetam o prompt de engenharia no campo do usuário.** Clicar em "Resumir reunião" cola 400+ caracteres de instrução ("Atue como um analista de reuniões sênior…") no textarea. O usuário vê a engenharia, não a ação. O envio por duplo clique é uma função oculta. O sexto card fica cortado em janelas de 800 px de altura sem indicação de rolagem (captura `01`).

**D11 — Sem tema claro e sem janela própria.** `color-scheme: dark` é fixo; em Windows com tema claro o assistente destoa de tudo ao redor. Abre numa aba comum do navegador, com `?token=` visível na URL até o redirecionamento, sem favicon (a aba mostra o globo genérico) e sem identidade de janela.

### Médios

**D12 — Markdown incompleto para o que os prompts pedem.** Os prompts de "Tarefas e ações" pedem tabela; `renderMarkdown()` não renderiza tabelas, então a resposta chega com barras verticais cruas. Não há citações ou blockquote, e o streaming mostra texto puro até o fim, causando um "salto" visual quando o markdown é aplicado.

**D13 — Estados e feedback inconsistentes.** Um único tipo de toast, sem ícone nem semântica (o erro é uma borda vermelha). Sem skeleton ao carregar. Erro de carga vira uma opção do `<select>` chamada "erro ao carregar". Ollama offline gera toast + opção + rodapé ao mesmo tempo.

**D14 — Vocabulário inconsistente.** "Transcrição" e "Reunião" designam a mesma coisa em lugares diferentes; "[vozes]"/"[texto]" na lista, "diarizado" na badge, "Separação de vozes" no menu; "com sua voz" e `VOCÊ`; "cópia criptografada (.tkpt)" e "modo protegido". Falta um glossário de produto.

**D15 — Ícone da bandeja sem legibilidade nem estados robustos.** Círculo `#1e293b` com microfone branco: quase invisível na barra de tarefas escura do Windows 11. Estados só por cor de fundo (inacessível para daltonismo), sem variante para barra clara, sem ICO multi-resolução gerado a partir de fonte vetorial versionada, sem hint de erro por forma.

**D16 — Tipografia sem escala.** Doze tamanhos distintos entre 10 e 22 px, letter-spacing de 1,6 px em rótulos de 10 px em caixa alta (difícil de ler), serifa apenas na marca e no título do estado vazio. Números sem `tabular-nums` na maior parte dos lugares.

**D17 — Efeitos sem função.** Glassmorphism (`backdrop-filter: blur(18px)`), três radiais de brilho, textura de ruído e glows coloridos em sombras. Custam GPU, competem com o conteúdo e datam a interface.

**D18 — Mobile como alvo errado.** O produto é um app local do Windows; o assistente abre em navegador desktop. Há três breakpoints e um drawer para 375 px, enquanto a janela mais comum (1366×768 ou 1920×1080 maximizada) recebe um chat de 700 px de largura e 60% de espaço vazio (captura `02`). A prioridade deveria ser densidade e uso do espaço em desktop, com mobile apenas como degradação sem quebra.

### Baixos

**D19 — Pareamento da extensão sem orientação.** Uma frase, um campo, um botão; sem passos, sem estado de sucesso visível além de um texto, sem ícone da extensão no manifest.

**D20 — Marca duplicada.** "Transkriptor" aparece na sidebar e no header mobile ao mesmo tempo em 860 px (captura `07`).

**D21 — Front-end monolítico.** `assistente.js` com 850 linhas sem módulos, estilos aplicados por JS (`wrap.style.display = 'flex'`), `chat.innerHTML` trocado ao mudar de reunião, testes que fixam substrings de CSS/JS (`test_v16_*`) e travam qualquer evolução visual.

**D22 — Nome do produto.** "Transkriptor" coincide com um serviço comercial de transcrição já existente. Não é problema técnico; é risco de confusão de marca. Decisão do usuário, registrada em `decisoes-usuario.md`.

## 3. Avaliação heurística (Nielsen), 1–5

| Heurística | Nota | Evidência principal |
|---|---|---|
| Visibilidade do estado do sistema | 3 | Tooltip e primeira linha do menu são bons; nada disso aparece no assistente; erro só por cor no ícone |
| Correspondência com o mundo real | 2 | `FALANTE_00`, "diarizado", "cluster", ".tkpt" expostos ao usuário |
| Controle e liberdade | 3 | Undo na correção existe; cancelar geração existe; `window.confirm` para exportar |
| Consistência e padrões | 1 | Cinco linguagens visuais (D03), três fluxos para renomear (D06) |
| Prevenção de erros | 4 | Consentimento fail-closed, confirmação de pausa, revisão otimista com 409 |
| Reconhecimento em vez de memória | 2 | Digitar `FALANTE_00` de cabeça; prompt colado no campo (D10) |
| Flexibilidade e eficiência | 3 | Ctrl+K, setas nos cards, Esc; sem paleta de comandos, sem atalhos no menu |
| Estética e design minimalista | 2 | Glow, ruído, blur, dourado + violeta; drawer sem design |
| Recuperação de erros | 3 | Mensagens existem, mas "erro ao carregar" dentro de um `<select>` |
| Ajuda e documentação | 3 | Manual completo, porém fora do produto; diagnóstico em .txt |

Média: 2,6 / 5. O produto é tecnicamente sério e visualmente amador nas bordas; a distância entre engenharia e apresentação é o problema central.

## 4. O que já está bom e deve ser preservado

- Consentimento explícito e fail-closed; nada grava antes do "Sim".
- Notificações silenciosas durante a reunião; estado no ícone e no tooltip.
- `aria-live`, `role="log"`, foco restaurado ao fechar o drawer, armadilha de Tab, `prefers-reduced-motion`, `forced-colors`.
- Cancelamento de geração no servidor, histórico por reunião, badge "com sua voz".
- Vocabulário de segurança honesto ("O TXT exportado é legível e contém dados sensíveis").
- Índice paginado, resultado estruturado com proveniência e revisão, tudo pronto para uma interface melhor consumir.

## 5. Direção recomendada (resumo)

1. **Uma linguagem para todas as superfícies.** Tokens de design em fonte única (`design/tokens.json`) gerando o CSS do assistente, as cores do ícone da bandeja e a página da extensão. Paleta grafite com um acento azul elétrico e cores semânticas de estado idênticas às do ícone. Sem serifa, sem dourado, sem glassmorphism.
2. **O assistente vira a Central do Transkriptor.** Um app shell com navegação lateral: Início (estado ao vivo, última reunião, fila), Reuniões (lista real, paginada, sem preview por padrão), Assistente, Participantes, Configurações e Diagnóstico. A bandeja permanece como lançador e indicador; deixa de ser a única interface.
3. **Desktop-first.** Janela ≥ 900 px é o alvo; conteúdo usa a largura; leitura em coluna de 72 caracteres; números tabulares; densidade profissional. Mobile continua sem quebra, mas não dita o layout.
4. **Tema claro e escuro** seguindo o Windows, com alternância persistida.
5. **Momentos nativos com dignidade.** Consentimento com ícone, hierarquia, DPI e contagem visual; ícone da bandeja vetorial com estados por forma e cor; menu reduzido a nove itens de topo com `checked` nativo.
6. **Corrigir os defeitos antes de redesenhar.** D01 (CSP) e o "Carregando…" preso são bugs, não design; entram na primeira fase.

Os detalhes normativos estão em `concept.md`, `design-system.md`, `spec.md`, `plan.md` e `tasks.md`.
