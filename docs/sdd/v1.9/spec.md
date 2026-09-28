# Spec — plataforma visual e Central do Transkriptor (SDD v1.9)

Fonte de versão do produto: `config.VERSAO`. IDs novos usam a série 14 (a v1.8 usa a série 13). Aprovar esta spec não marca tarefas como executadas nem autoriza implementação; ver `decisoes-usuario.md`.

Contratos de arquivos, tokens, DOM e API estão em `interfaces.md`; a especificação visual em `design-system.md`; o protocolo de execução em `executor-llm.md`. Divergência descoberta durante a implementação exige emenda nos documentos antes de código incompatível.

## Invariantes globais

- Tudo da v1.8 continua valendo: Python 3.12+, UTF-8/PT-BR, constantes em `config.py`, `Transcritor` único, nenhum callback sob lock do ciclo, serviços em `127.0.0.1`, processamento local, consentimento antes de captura, testes isolados de dados reais, arquivos Python ≤ 500 linhas.
- Nenhuma requisição de rede fora de `127.0.0.1`; nenhuma fonte, script, estilo ou imagem externa. A CSP endurecida é a prova.
- Nenhum estilo inline (`style=`), nenhum `<style>` ou `<script>` inline no HTML servido; JS manipula classes, não `style`.
- Nenhum conteúdo de fala, nome de participante, token, chave ou caminho pessoal em `/api/estado`, em logs, em capturas de evidência ou em listas por padrão.
- Toda cor, espaço, raio, sombra e duração vem de token `--tk-*` gerado de `design/tokens.json`; o Python do ícone lê os mesmos valores.
- Testes E2E rodam sobre o HTML/CSS/JS reais e, para a Central, também sob a CSP real; testes de substring podem ser substituídos por comportamentais na mesma task, nunca simplesmente apagados.
- Toda task termina com teste específico, regressão e evidência com capturas sintéticas. Falha bloqueia avanço.

## Requisitos e rastreabilidade

| Requisito | Comportamento verificável | Tarefa |
|---|---|---|
| UX-14.A1 | Tokens em fonte única JSON geram `tokens.css` (temas claro/escuro) e `design_tokens.py`; teste prova sincronia e contraste AA de todos os pares texto/fundo e 3:1 para controles; testes legados de substring migrados. | T-14.A1 |
| SEC-14.A2 | CSP explícita por diretiva sem `unsafe-inline`; HTML sem `style=`; `data:` só em `img-src`; favicon local; teste E2E carrega a página sob a CSP real e reprova qualquer violação de console. | T-14.A2 |
| UX-14.A3 | Base tipográfica, sprite de ícones e componentes `tk-*` com todos os estados em galeria; snapshot visual sintético por componente; sem `backdrop-filter`, glow, serifa ou emoji. | T-14.A3 |
| UX-14.B1 | App shell com navegação lateral, barra superior com estado espelhado da bandeja, alternância de tema persistida e abertura opcional em janela de app; nenhuma marca duplicada em qualquer largura. | T-14.B1 |
| UX-14.B2 | Lista de reuniões consome o índice paginado, sem fala por padrão, com busca, filtros, estados vazio/carregando/erro, seleção preservada ao filtrar e navegação por teclado completa. | T-14.B2 |
| UX-14.B3 | Conversa em coluna de leitura, markdown com tabelas e código, streaming sem salto visual, ações rápidas como chips de intenção sem colar prompt no campo, ações por mensagem e clipboard com erro visível. | T-14.B3 |
| UX-14.B4 | Toasts tipados, skeletons, estados de Ollama offline e transcrição longa com próximo passo; nenhuma mensagem de erro dentro de controles de seleção. | T-14.B4 |
| UX-14.C1 | Painel de participantes lista falantes com nome amigável, cor, contagem, estado e origem; `FALANTE_XX` nunca aparece sem nome amigável; "Carregando" some após carregar. | T-14.C1 |
| UX-14.C2 | Linha do tempo de segmentos filtrável, sugestões com confirmar/escolher, correção com undo, versão visível, 409 tratado sem perder o painel, conteúdo escapado. | T-14.C2 |
| UX-14.C3 | Exportação legível com diálogo próprio e texto de consequência; correção por reunião e aprendizado de voz unificados na Central com distinção explícita; diálogos Tk correspondentes removidos e menu apontando para a Central. | T-14.C3 |
| FR-14.D1 | `/api/estado` publica snapshot sem lock e sem dados sensíveis; página Início mostra estado ao vivo, última reunião, proteção efetiva e cinco últimas reuniões; polling para quando a aba está oculta. | T-14.D1 |
| FR-14.D2 | Configurações na Central cobrem os toggles do menu com as mesmas regras, confirmações e persistência; mutações exigem header secreto; menu da bandeja reduzido e sem regressão funcional. | T-14.D2 |
| FR-14.D3 | Diagnóstico renderizado na Central com os mesmos itens, ações sugeridas e exportação sem PII; retranscrição de áudio retido pela Central; diálogos Tk removidos. | T-14.D3 |
| UX-14.E1 | Ícone vetorial versionado gera ICO multi-resolução, PNGs por estado e favicon; estados distinguíveis por forma; cores iguais aos tokens; fallback PIL preservado. | T-14.E1 |
| UX-14.E2 | Menu da bandeja com no máximo nove itens de topo, "Abrir Transkriptor" primeiro, estado com o mesmo vocabulário da Central, `checked` nativo em vez de prefixo textual; testes de menu migrados. | T-14.E2 |
| UX-14.E3 | Consentimento com DPI tratado, ícone, hierarquia, fonte detectada e contagem visual; garantias fail-closed, timeout e testes existentes inalterados. | T-14.E3 |
| UX-14.E4 | Confirmações de pausa, saída e modo protegido com texto de consequência padronizado; na Central via diálogo próprio; na bandeja via `MessageBoxW` com o mesmo texto. | T-14.E4 |
| UX-14.E5 | Página de pareamento com tokens copiados, passos numerados, estados de sucesso e erro, ícones no manifest; sem rede externa. | T-14.E5 |
| NFR-14.F1 | Gate de acessibilidade: axe sem violações sérias em todas as páginas, teclado completo, roteiro de Narrador executado, `forced-colors` e `reduced-motion` verificados, 375/900/1366/1920 sem overflow. | T-14.F1 |
| NFR-14.F2 | Orçamento de front: CSS ≤ 80 KB, JS ≤ 150 KB, zero requisições externas sob CSP, primeira renderização da Central < 300 ms local; teste falha ao exceder. | T-14.F2 |
| NFR-14.G1 | Manual com capturas sintéticas de todas as superfícies, glossário, evidências por task, gate visual completo e decisão de versão registrada; sem bump automático. | T-14.G1 |

## Contratos resumidos

Detalhes em `interfaces.md`. Pontos que a implementação não pode reinterpretar:

- `design/tokens.json` é a única fonte de cor/tipo/espaço. `scripts/gerar_tokens.py` escreve `static/css/tokens.css` e `design_tokens.py`; `estado_icone.py` importa cores de `design_tokens.py`.
- CSP normativa: `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`. O teste de segurança existente continua verificando `frame-ancestors 'none'`.
- Snapshot de estado: `{"estado": "aguardando|gravando|processando|separando_vozes|pausado|erro", "rotulo": str, "fontes": [str], "processamento": str|null, "protecao": "compatible|protected", "ultima_reuniao": {"meeting_id": str, "started_at": str, "estado": str}|null, "versao": str, "gerado_em": str}`. Nada além disso.
- IDs de DOM listados em `interfaces.md` são estáveis; mudanças de controle migram os testes na mesma task.
- Vocabulário de estados e badges segue o glossário de `design-system.md`.

## Limites e metas

- Contraste: texto ≥ 4,5:1; texto grande (≥ 18,66 px negrito ou ≥ 24 px) ≥ 3:1; ícones e bordas de controle ≥ 3:1. Calculado sobre os tokens de ambos os temas.
- Larguras verificadas: 375 (sem quebra), 900 (mínimo confortável), 1366 e 1920 (alvo). Sem overflow horizontal em nenhuma.
- Movimento: nenhuma transição acima de 240 ms; nenhuma animação infinita fora de progresso; `prefers-reduced-motion` zera.
- Polling de estado: 2 s com aba visível; suspenso com `document.hidden`; nenhuma leitura de disco no snapshot além do que já está em memória, exceto a última reunião via índice.
- Orçamento: CSS total ≤ 80 KB, JS total ≤ 150 KB, sprite ≤ 40 KB, ICO ≤ 120 KB. Sem minificação obrigatória; o orçamento vale sobre os arquivos servidos.
- Menu da bandeja: ≤ 9 itens de topo, ≤ 2 níveis.
- Consentimento: legível a 100 %, 150 % e 200 % de escala do Windows; botão "Sim" com área ≥ 32 px de altura lógica; contagem visível por barra e por texto.
- Galeria e capturas usam apenas dados sintéticos definidos em `tests/e2e/fixtures/`.

## Compatibilidade e migração

- Nenhum contrato de dados, rota existente ou formato de arquivo muda. Rotas novas são aditivas.
- Testes legados que fixam substrings de CSS/JS/HTML (`tests/test_v16_a_tokens.py`, `tests/test_v16_b_assistente.py`, `tests/test_v16_c_a11y.py`, `tests/test_v16_g_qualidade.py`, partes de `tests/test_assistente_api.py`, `tests/test_v16_d_bandeja.py`) são migrados para verificações comportamentais ou de contrato na task que altera o alvo, com a lista exata na evidência.
- O menu da bandeja preserva todas as funções; itens migrados para a Central mantêm uma entrada "Abrir Transkriptor" que abre a página correspondente.
- Diálogos Tk removidos só depois da rota equivalente da Central estar verde e evidenciada; a remoção é parte da mesma task para não deixar dois caminhos.
- `config.VERSAO` não muda nesta proposta.
