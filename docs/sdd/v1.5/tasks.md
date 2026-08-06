# Tasks — Transkriptor v1.5

Status inicial: ⬜ pendente. Cada tarefa termina com o teste listado e commit.

| ID | Entrega | Spec | Teste obrigatório ao final | Status |
|---|---|---|---|---|
| T-10.A1 | persistência dedicada da chave e merge de config | SEC-10.F1/F2 | config + crypto | ✅ |
| T-10.A2 | isolamento integral dos testes de estado local | SEC-10.F3 | testes de isolamento | ✅ |
| T-10.B1 | microfone nunca inicia reunião | FR-10.A1/A3 | detecção multi-fonte | ✅ |
| T-10.B2 | fim limitado sem fonte forte | FR-10.A2/A4 | detecção + integração | ✅ |
| T-10.C1 | consentimento antes da captura e timeout negativo | FR-10.B1/B2/B3 | aviso de gravação | ✅ |
| T-10.C2 | remover toast ao vivo e backend `plyer` | UX-10.B1/B2 | notificador + bandeja | ✅ |
| T-10.D1 | modo de captura posterior sem Whisper | FR/NFR-10.C* | gravação posterior | ✅ |
| T-10.D2 | flush, métricas e watchdog do modo leve | FR-10.C2/C3 | gravação + watchdog | ✅ |
| T-10.E1 | fila durável atômica e retomada | FR-10.D1/D2/D4 | fila | ✅ |
| T-10.E2 | subprocesso posterior e `.txt` atômico | FR-10.D3, FR-10.E* | processador + retranscritor | ✅ |
| T-10.F1 | integrar ciclo completo no app/menu | FR-10.A4, FR-10.E4 | fluxo v1.5 | ✅ |
| T-10.F2 | versão, manual e gates de recursos | NFR-10.C*, H1 | versão/manual/recursos | ⬜ |
| T-10.G1 | extrator genérico e seguro de intervalos | FR-10.G1 | recuperação | ⬜ |
| T-10.G2 | recuperar e retranscrever as duas reuniões | FR-10.G2/G3 | auditoria de artefatos | ⬜ |
| T-10.H1 | auditoria final de qualidade/coerência/segurança | NFR-10.H* | suíte + Windows + diff | ⬜ |

Nenhuma tarefa pode ser marcada ✅ apenas porque o código existe. O teste final
da linha, o commit e a evidência correspondente precisam existir.

## Evidências de execução

- **T-10.A1:** RED confirmado nos dois comportamentos ausentes; GREEN com
  `21 passed` em configuração/criptografia e regressão de bootstrap com
  `15 passed`.
- **T-10.A2:** RED por ausência do guard; GREEN no subprocesso controlado e
  suíte integral com `325 passed`. O guard resolveu o checkout real como
  `C:\Projetos\transkriptor` e comparou config, chave, transcrições e atalhos.
- **T-10.B1:** RED confirmou início indevido no quarto ciclo fraco; GREEN com
  `38 passed`, incluindo 120 ciclos contínuos de microfone sem iniciar reunião.
- **T-10.B2:** RED confirmou que microfone mantinha a sessão e heartbeat não
  distinguia confiança; GREEN com `42 passed`, encerrando no sexto ciclo sem
  título/extensão e mantendo a extensão forte em segundo plano.
- **T-10.C1:** RED confirmou a autorização permissiva e a captura anterior à
  resposta; GREEN com `16 passed` no fluxo consentimento/integração e `14 passed`
  de regressão da bandeja. Apenas Sim autoriza; Não, timeout e erro não capturam.
- **T-10.C2:** RED confirmou ausência de reutilização do ícone e dependência
  residual; GREEN no canal silencioso e gate integral da fase com `330 passed`.
  Startup não abre balão e notificação padrão não cria janela ou ícone.
- **T-10.D1:** RED por ausência do modo posterior; GREEN com `18 passed` no gate
  captura/WAV/stop e `20 passed` na regressão de seleção de modelo. O import do
  núcleo de captura não importa bibliotecas de IA.
- **T-10.D2:** quatro REDs para métricas, flush, watchdog e diagnóstico; GREEN
  com `38 passed`. O primeiro gate integral encontrou apenas o limite estrutural
  de linhas (`337 passed`); extração coesa para `captura_leve.py` corrigiu o
  residual, com gate dirigido posterior de `39 passed` e integral de
  `338 passed`.
- **T-10.E1:** RED por módulo inexistente; GREEN com `9 passed` cobrindo
  atomicidade, estados, retomada, allowlist de metadados e rejeição de paths
  fora de `transcricoes/`.
- **T-10.E2:** RED por worker inexistente; GREEN com `9 passed` no processador,
  retranscritor e criptografia. Saída principal `.txt` tem timestamps relativos,
  cópia `.tkpt` adicional e subprocesso Windows sem janela/prioridade baixa;
  gate integral da fase com `351 passed`.
- **T-10.F1:** RED confirmou que o app ainda não solicitava o modo posterior;
  GREEN com `29 passed` no gate dirigido e `355 passed` na suíte integral.
  O fim da reunião libera a captura, cria job durável e inicia um único worker;
  a bandeja mostra os quatro estados. O comando e o estado interno de captura
  manual foram removidos, e falha anterior ao claim não entra em laço de restart.

