# Roteiro de leitor de tela — Central do Transkriptor (NFR-14.F1)

Objetivo: confirmar que cada superfície é operável e compreensível só com teclado e leitor de tela (Narrador do Windows, `Win+Ctrl+Enter`). Dados sempre sintéticos (fixtures de `tests/e2e/fixtures/central.js`); nada é gravado nem exportado de verdade.

## Preparação

1. Abrir a Central pela bandeja (**Abrir Transkriptor**) ou `python assistente.py` com `TRANSKRIPTOR_GALERIA=1` para a galeria.
2. Ligar o Narrador. Modo de varredura (`Caps Lock+Espaço`) para ler; `Tab`/`Shift+Tab` para controles; `H` para pular por títulos; `D` por marcos (landmarks).
3. Tema: repetir uma vez em escuro e uma vez em claro (`#tema-toggle`, anunciado como "Alternar tema").

## Percurso por página (o que deve ser anunciado)

| # | Página | Passos | Anúncio esperado | Resultado |
|---|--------|--------|------------------|-----------|
| 1 | Shell (todas) | `D` pelos marcos | "navegação Principal", "principal" (conteúdo), "barra de status" com o estado atual (ex.: "Aguardando reunião") | ver abaixo |
| 2 | Shell | `Tab` a partir do topo | link "Pular para o conteúdo" primeiro; depois marca, itens da navegação com nome (Início, Reuniões, Assistente, Participantes, Configurações, Diagnóstico), alternar tema | ver abaixo |
| 3 | Início | `H` | título "Início"; cartões com nome e valor (Estado, Reuniões, Proteção); lista "Últimas reuniões" com data e ação "Abrir no Assistente" | ver abaixo |
| 4 | Reuniões | `Tab` até a listbox, setas | "Reuniões, lista, N itens"; cada opção com data, duração, estado (Protegida/Legível, Separar vozes); `Enter` abre no Assistente; busca com rótulo "Buscar reunião" | ver abaixo |
| 5 | Assistente | `Tab` | listbox de reuniões; combobox "Modelo"; chips de prompt com nome; área de texto "Pergunta" com dica; botão "Enviar"; região de log `role=log` anuncia respostas novas (`aria-live=polite`); `Esc` cancela geração ("Parar" some) | ver abaixo |
| 6 | Participantes | `Tab` | combobox "Reunião"; lista de falantes com nome, origem e confiança; botões "Confirmar …"/"Escolher outro nome"; formulário de correção com rótulos; "Exportar texto legível" abre diálogo modal com título e consequência, foco preso no diálogo, `Esc` fecha e devolve o foco | ver abaixo |
| 7 | Configurações | `Tab` | cada opção é `switch` com nome e consequência lida (`aria-describedby`); desligar "Gravação automática" abre diálogo "Pausar a gravação automática?" com botão padrão "Cancelar" | ver abaixo |
| 8 | Diagnóstico | `Tab` | botão "Rodar diagnóstico"; resultado em região `role=status`; tabela/lista de fontes com título e classe de janela; áudios retidos com ação "Retranscrever" | ver abaixo |
| 9 | Galeria | `H` | uma seção por componente com título; estados de listbox anunciados ("Vazia", "Sem resultado", "Erro" como listas simples); toasts estáticos ignorados (`aria-hidden`) | ver abaixo |
| 10 | Diálogos/toasts | disparar | toast anunciado uma vez (`role=status`); diálogo anuncia título e consequência ao abrir | ver abaixo |

## Execução registrada

**24/09/2026 — automatizada (Playwright, Chromium 1366×900, fixtures sintéticas):**

- `node docs/sdd/v1.9/evidencias/T-14.F1/aria_snapshots.js` gerou `T-14.F1/aria/<pagina>.yaml` com a árvore de acessibilidade de cada página (papéis, nomes e estados, o insumo do que um leitor de tela anuncia). Resultado: 7 páginas, **0 controles sem nome acessível** (button/link/textbox/combobox/listbox/checkbox/switch sem nome).
- `tests/e2e/accessibility.spec.js` (foco visível em todos os controles, 7 páginas): Tab alcança todos os controles focáveis, nenhum sem anel de foco, o foco só sai do documento uma vez por ciclo. **10 passed.**
- `tests/e2e/axe.spec.js` (wcag2a/aa, wcag21a/aa, best-practice; 7 páginas × dark/light × forced-colors+reduced-motion): **0 violações serious/critical**; relatório em `T-14.F1/axe-relatorio.json`.
- `tests/e2e/larguras.spec.js` (375/900/1366/1920): sem overflow, sem elemento além da borda, sem texto cortado. **28 passed.**

**Execução com o Narrador do Windows (sessão interativa):** _pendente_ — exige o app rodando na sessão do usuário com o Narrador ligado; este roteiro é o que deve ser seguido e a coluna "Resultado" preenchida com data. As linhas 1–10 têm o anúncio esperado derivado dos snapshots ARIA (mesma árvore que o Narrador consome via UIA/Chromium), mas a leitura real (ordem, verbosidade, pausas) só é validada ao vivo.

## Critério de aprovação

Todas as linhas com "OK" e data; qualquer anúncio vazio, controle inalcançável por teclado, foco perdido ao fechar diálogo ou toast repetido é defeito a corrigir antes de fechar F14.G.
