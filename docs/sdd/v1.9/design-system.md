# Design system — Transkriptor (SDD v1.9)

Especificação visual normativa. Os nomes de tokens aqui são os nomes do contrato em `interfaces.md`; valores podem ser ajustados durante T-14.A1 desde que os testes de contraste continuem verdes e a mudança seja registrada na evidência.

## 1. Princípios de aplicação

- Toda cor, espaço, raio, sombra e duração em CSS vem de um token `--tk-*`. Hex solto fora de `tokens.css` é reprovado por teste.
- Tema escuro é o padrão em `prefers-color-scheme: dark`; claro em `light`; `data-theme="light|dark"` no `<html>` força a escolha e é persistido em `localStorage`.
- Nenhum recurso externo: fontes do sistema, ícones em sprite local, imagens `data:` só em `img-src` explícito.
- Desktop-first: layout projetado em 1366 e 1920 px; 900 px é o mínimo confortável; 375 px é degradação sem quebra.

## 2. Cor

### Paleta base (grafite) e acento

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `--tk-bg-0` | `#0F1115` | `#F5F6F8` | Fundo da janela |
| `--tk-bg-1` | `#151821` | `#FFFFFF` | Superfície principal (painéis, cards) |
| `--tk-bg-2` | `#1B1F2A` | `#EEF0F4` | Superfície elevada, hover, campos |
| `--tk-bg-3` | `#232837` | `#E3E6EC` | Pressionado, selecionado |
| `--tk-border` | `rgba(255,255,255,0.08)` | `rgba(15,17,21,0.10)` | Bordas padrão |
| `--tk-border-strong` | `#626A7A` | `#858E9F` | Bordas de campos em foco/hover (sólida; ≥ 3:1 sobre `bg-1`) |
| `--tk-text-1` | `#E8EAF0` | `#14171F` | Texto principal |
| `--tk-text-2` | `#B0B6C3` | `#3E4553` | Texto secundário |
| `--tk-text-3` | `#828A9A` | `#5F6A7E` | Rótulos, metadados (mínimo 4,5:1 sobre `bg-1` e `bg-2`) |
| `--tk-accent` | `#4F8CFF` | `#1F5FD6` | Links, ícones ativos, foco, texto de destaque |
| `--tk-accent-fill` | `#2F6FE8` | `#1F5FD6` | Fundo de botão primário (texto branco ≥ 4,5:1) |
| `--tk-accent-soft` | `rgba(79,140,255,0.14)` | `rgba(31,95,214,0.10)` | Seleção, fundo de chip ativo |
| `--tk-on-accent` | `#FFFFFF` | `#FFFFFF` | Texto sobre `accent-fill` |
| `--tk-danger` / `--tk-danger-fill` / `--tk-danger-soft` | `#F87171` / `#DC2626` / `rgba(239,68,68,0.12)` | `#B91C1C` / `#DC2626` / `rgba(220,38,38,0.08)` | Texto, botão e fundo de erro |
| `--tk-focus` | `rgba(79,140,255,0.35)` | `rgba(31,95,214,0.35)` | Halo de foco em campos |
| `--tk-scrim` | `rgba(0,0,0,0.55)` | `rgba(15,17,21,0.45)` | Fundo de overlay/drawer |

Contrastes medidos pelo gerador (escuro): `text-1`/`bg-1` 14,7:1; `text-2`/`bg-1` 8,7:1; `text-3`/`bg-1` 5,1:1 e sobre `bg-2` 4,7:1; `accent`/`bg-1` 5,5:1; `on-accent`/`accent-fill` 4,6:1. Claro: `text-3`/`bg-1` 5,5:1; `accent`/`bg-1` 5,7:1. O teste `tests/test_design_tokens.py` recalcula esses valores e reprova qualquer par abaixo de 4,5:1 (texto) ou 3:1 (bordas de controle e ícones).

### Estados semânticos (compartilhados com o ícone da bandeja)

| Token | Valor | Estado do produto | Ícone |
|---|---|---|---|
| `--tk-state-idle` | `#5B6B8C` | Aguardando reunião | fundo azul-acinzentado, microfone |
| `--tk-state-recording` | `#22C55E` | Gravando | fundo verde, microfone, ponto branco pulsante só na Central |
| `--tk-state-processing` | `#8B5CF6` | Processando reunião | fundo violeta, microfone com engrenagem |
| `--tk-state-diarizing` | `#F59E0B` | Separando vozes | fundo âmbar, microfone com duas ondas |
| `--tk-state-paused` | `#64748B` | Pausado | fundo cinza, microfone cortado |
| `--tk-state-error` | `#EF4444` | Erro | fundo vermelho, microfone com "!" |

Em texto sobre fundo escuro, cada estado tem variante `-text` calculada para ≥ 4,5:1 (por exemplo `--tk-state-recording-text: #4ADE80`). Estados nunca são comunicados só por cor: sempre há ícone com forma distinta e rótulo.

### Proteção e privacidade

| Token | Uso |
|---|---|
| `--tk-protect` (`#14B8A6` / `#0F766E`) | Badge "Protegida" (resultado cifrado) |
| `--tk-warn` (`#F59E0B` / `#B45309`) | Badge "Legível", avisos de exportação, transcrição longa |

## 3. Tipografia

```
--tk-font-sans: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
--tk-font-display: "Segoe UI Variable Display", "Segoe UI", system-ui, sans-serif;
--tk-font-mono: "Cascadia Code", "Cascadia Mono", Consolas, ui-monospace, monospace;
```

| Token | Tamanho/entrelinha | Peso | Uso |
|---|---|---|---|
| `--tk-type-xs` | 12/16 | 500 | Rótulos de campo, badges (caixa alta, letter-spacing 0,4 px, nunca 1,6 px) |
| `--tk-type-sm` | 13/18 | 400 | Metadados, dicas, tabelas densas |
| `--tk-type-md` | 14/20 | 400 | Corpo, chat, formulários |
| `--tk-type-lg` | 16/24 | 500 | Títulos de card, itens de navegação |
| `--tk-type-xl` | 20/28 | 600 | Título de página |
| `--tk-type-2xl` | 24/32 | 600 | Título de estado vazio |
| `--tk-type-3xl` | 32/40 | 600 | Números de destaque no Início |

`font-variant-numeric: tabular-nums` em qualquer número que mude (tempo, tamanhos, contadores). Coluna de leitura do chat: `max-width: 72ch`. Sem itálico decorativo; ênfase por peso 600 ou cor `text-1`.

## 4. Espaço, raio, elevação, movimento

- Espaço em base 4: `--tk-space-1..8` = 4, 8, 12, 16, 24, 32, 48, 64 px. Padding de painel 24 px; de card 16 px; de linha de lista 12 px vertical.
- Raio: `--tk-radius-sm` 6 px (chips, badges), `--tk-radius-md` 10 px (campos, botões, cards), `--tk-radius-lg` 14 px (painéis, diálogos), `--tk-radius-pill` 999 px.
- Elevação: `--tk-elev-0` nenhuma; `--tk-elev-1` `0 1px 2px rgba(0,0,0,.24)` (cards); `--tk-elev-2` `0 8px 24px rgba(0,0,0,.32)` (painéis, menus); `--tk-elev-3` `0 16px 48px rgba(0,0,0,.40)` (diálogos). Sem sombras coloridas, sem `backdrop-filter`.
- Movimento: `--tk-dur-fast` 120 ms, `--tk-dur-base` 180 ms, `--tk-dur-slow` 240 ms; easing `cubic-bezier(0.2, 0, 0, 1)`. Proibidos `bounce`, `elastic`, animação infinita fora de indicadores de progresso. `prefers-reduced-motion` zera durações.
- Foco: anel de dois tons `0 0 0 2px var(--tk-bg-1), 0 0 0 4px var(--tk-accent)`, visível em ambos os temas e em `forced-colors`.

## 5. Ícones

- Sprite `static/icones.svg` com `<symbol id="i-…">`, viewBox 20, traço 1,5 px, `stroke: currentColor`, cantos arredondados. Uso: `<svg class="tk-icon"><use href="/static/icones.svg#i-mic"/></svg>`.
- Conjunto mínimo: mic, mic-off, wave, gear, folder, file-text, shield, shield-check, lock, unlock, users, user, clock, play, stop, refresh, check, x, alert, info, search, chevron, menu, sun, moon, copy, download, external, sparkles (assistente), list, layout.
- Sem emoji em interface. Sem caracteres tipográficos como ícones.

## 6. Componentes

Cada componente tem classes `tk-*`, estados obrigatórios e regra de acessibilidade. Uma página de galeria (`/galeria`, ativa só quando `TRANSKRIPTOR_GALERIA=1`) renderiza todos os componentes em todos os estados para revisão visual e captura.

| Componente | Estados obrigatórios | Regra |
|---|---|---|
| Botão (`tk-btn`, variantes `--primary`, `--secondary`, `--quiet`, `--danger`) | default, hover, active, focus-visible, disabled, loading | Altura 36 px; ícone opcional 16 px; loading troca o rótulo por spinner sem mudar largura |
| Campo (`tk-field`) | default, hover, focus, invalid, disabled | Rótulo sempre visível acima; mensagem de erro abaixo com `aria-describedby` |
| Seleção (`tk-select`) | idem campo | Só para listas curtas (modelo Ollama, reunião no painel) |
| Listbox (`tk-listbox`) | vazio, carregando (skeleton), erro, com itens, filtrado sem resultado | `role="listbox"`/`option`, setas, Home/End, digitação incremental; seleção persiste ao filtrar |
| Badge de estado (`tk-badge-state`) | um por estado semântico | Ícone + texto; cor pelo token de estado |
| Badge de proteção (`tk-badge-protect`) | protegida, legível, com sua voz | Ícone `shield`/`unlock`/`user` |
| Toast (`tk-toast`) | info, success, warning, error | Ícone, título, texto opcional, fechar; `role="status"` ou `alert`; 4 s, erro persiste |
| Diálogo (`tk-dialog`) | confirmação, perigo, formulário | `<dialog>` nativo, foco inicial no botão seguro, Esc cancela, texto de consequência obrigatório em ações de perigo |
| Painel lateral (`tk-panel`) | fechado, aberto, carregando | 420 px, empurra o conteúdo em ≥ 1200 px, sobrepõe abaixo; foco restaurado ao fechar |
| Skeleton (`tk-skeleton`) | — | Mesmas dimensões do conteúdo final; `aria-hidden` |
| Estado vazio (`tk-empty`) | primeiro uso, sem resultado de filtro, erro | Ícone, título, uma frase, uma ação primária |
| Linha de dados (`tk-row`) | default, hover, selecionada, com ação | Grid de colunas fixas; texto com `text-overflow` e `title` |
| Progresso (`tk-progress`) | determinado, indeterminado | `role="progressbar"`; indeterminado só com rótulo textual ao lado |
| Chip de intenção (`tk-chip`) | default, hover, ativo, disabled | Ações rápidas do assistente: rótulo curto; prompt fica em `data-intent`, nunca no campo |
| Barra de estado (`tk-statusbar`) | um por estado semântico | Espelha o ícone da bandeja na Central; polling de 2 s |

## 7. Layout da Central

- App shell: `nav` lateral fixa de 240 px (colapsa para 64 px com ícones em < 1200 px; vira drawer em < 900 px), barra superior de 56 px com título da página, barra de estado e alternância de tema; área de conteúdo com `max-width: 1280px` e padding 24 px.
- Navegação: Início, Reuniões, Assistente, Participantes, Configurações, Diagnóstico. Item ativo com `aria-current="page"`.
- Assistente: coluna de conversa `max-width: 72ch` centrada; composer fixo embaixo; chips de intenção acima do composer; contexto da reunião ativa em uma linha acima da conversa com badge de proteção e botão "Trocar".
- Participantes: painel lateral aberto a partir do Assistente e página própria em Participantes; lista de falantes à esquerda (nome, cor, número de falas, estado), linha do tempo de segmentos à direita com filtro por falante.
- Início: três cartões de estado (o que o app está fazendo agora; última reunião com estado do processamento; proteção efetiva) e lista das cinco últimas reuniões.

## 8. Ícone da bandeja e marca

- Símbolo: microfone geométrico dentro de um quadrado arredondado (não círculo), com uma barra de onda à direita. Fonte vetorial `design/icone/transkriptor.svg`, versionada.
- Estados: fundo pelo token de estado; a forma muda (ponto, engrenagem, ondas, corte, exclamação) para não depender de cor. Variante de contorno claro para barra de tarefas clara.
- Gerador `scripts/gerar_icones.py` produz `transkriptor.ico` (16, 20, 24, 32, 48, 256) e `static/icones/bandeja/<estado>.png` (16, 32, 64) e o favicon `static/favicon.ico`. `bandeja_icone.py` carrega os PNGs e cai no desenho PIL só se os arquivos faltarem.
- Wordmark: "Transkriptor" em `--tk-font-display` 600, sem serifa, sem dourado; subtítulo "Reuniões locais" em `text-3`.

## 9. Microcopy e glossário

| Termo na interface | Significado | Não usar |
|---|---|---|
| Reunião | Item de lista com data, duração, estado | "transcrição" como nome do item |
| Transcrição | O texto produzido de uma reunião | "txt" |
| Falante 1, 2… | Cluster acústico ainda sem nome | `FALANTE_00` sozinho |
| Participante | Pessoa identificada pelo Meet ou pelo usuário | "cluster", "roster" |
| VOCÊ | O usuário identificado pelo perfil de voz | "identificar minha voz" sem contexto |
| Identificação pendente | Sem evidência suficiente para nomear | "incerto", "unknown" |
| Sugestão | Nome proposto com origem e confiança | "assignment" |
| Protegida / Legível | Resultado cifrado / em texto claro | ".tkpt", "criptografada" como badge |
| Separar vozes | Diarização | "diarizado" como badge |
| Separação de vozes | Etapa de processamento | — |
| Gravando · Processando · Separando vozes · Aguardando · Pausado · Erro | Estados do produto | variações ("Transcrevendo", "PAUSADO — não está gravando") |

Regras: frases curtas, verbo no início das ações ("Gravar esta reunião", "Exportar texto legível"), consequência explícita em ações irreversíveis, nada de reticências como sinal de "abre tela" (usar seta ou ícone). Erros dizem o que aconteceu e o próximo passo; nunca só "Erro: …".
