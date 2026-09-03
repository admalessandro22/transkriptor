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
| T-10.F2 | versão, manual e gates de recursos | NFR-10.C*, H1 | versão/manual/recursos | ✅ |
| T-10.G1 | extrator genérico e seguro de intervalos | FR-10.G1 | recuperação | ✅ |
| T-10.G2 | recuperar e retranscrever as duas reuniões | FR-10.G2/G3 | auditoria de artefatos | ✅ |
| T-10.H1 | auditoria final de qualidade/coerência/segurança | NFR-10.H* | suíte + Windows + diff | ✅ |
| T-10.H2 | tornar o consentimento Zoom visível e foreground | FR-10.B1 | aviso + teste Windows | ✅ |
| T-10.H3 | reconhecer título atual `Meet: ...` do Chrome | FR-10.A3 | detecção multi-fonte | ✅ |
| T-10.H4 | rastreabilidade segura do worker e fechamento operacional | NFR-10.H3/H4, SEC-10.F4 | observabilidade + gates Windows | ✅ |

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
- **T-10.F2:** RED confirmou versão 1.4, PDF antigo e ausência do gate de
  recursos; GREEN com `12 passed`, gate `v1.5-estatico` com `17 passed` e suíte
  integral com `359 passed`. O manual v1.5 foi extraído e renderizado em 7
  páginas sem páginas vazias ou defeitos visuais. O coletor Win32 de working set,
  CPU de um núcleo e classes pystray foi exercitado em processo controlado; o
  gate real de 10 minutos foi repetido no fechamento Windows de T-10.H1 em
  processo isolado, sem reunião: uma instância/ícone, crescimento de 0,145 MB
  e CPU média de 0,044%.
- **T-10.G1:** RED por ferramenta inexistente; GREEN com `10 passed` para
  duração/frames, limites finitos, WAV inválido, colisão, streaming limitado e
  SHA-256 imutável da origem. A publicação usa hard link exclusivo do temporário
  validado, portanto não sobrescreve destino nem expõe arquivo parcial.
- **T-10.G2:** as duas reuniões foram extraídas e processadas separadamente com
  Whisper `medium`; `29 passed` no gate dirigido após regressões para a lacuna de
  285 s, explosão de clusters e intervalo visual zero. A auditoria confirmou
  hashes, WAV mono/16 kHz, 815/136 segmentos, UTF-8, ordem temporal, conteúdo
  idêntico entre TXT simples e diarizado, jobs `ready` e ausência de fala em
  JSON/log. Só depois disso os 979.463.830 bytes combinados/indevidos e o `.tkpt`
  ilegível foram movidos para a Lixeira. Evidência detalhada em
  `recuperacao-2026-08-06.md`.
- **T-10.H1:** correções finais para pausa concorrente, leitura criptografada
  sem WAV plaintext no TEMP, colisões de nomes/retenção e avanço da fila após
  falha. Teste dirigido `41 passed`; suíte completa `377 passed`; verificador
  de fases `all` exit 0; `compileall` exit 0; processo Windows controlado por
  600 s com um ícone, 0,145 MB de crescimento e CPU média de 0,044%; bipes
  fora de Meet não produziram áudio/job. Auditoria detalhada em
  `auditoria-final-2026-08-06.md`. A sessão humana de dez minutos e a escuta
  palavra por palavra permanecem limitações declaradas.
- **T-10.H2:** diagnóstico de 2026-08-07 confirmou que o Zoom foi detectado,
  mas a `MessageBoxTimeoutW` modal desabilitava a janela dona e podia ficar
  invisível atrás dela. A caixa foi substituída por uma janela Win32 própria,
  `TOPMOST`/`TOOLWINDOW`, sem owner modal: botões Sim/Não, X como Não e timeout
  fail-closed. Teste dirigido `18 passed`, suíte integral `379 passed`; ensaio
  Windows manteve o Chrome habilitado antes/depois de clicar fora, encontrou a
  janela visível/topmost e fechou sem HWND órfão.
- **T-10.H3:** o histórico do Chrome registrou a reunião de 2026-08-07 como
  `Meet: Reunião bolsistas PROINOVE - Projeto Sistema de Incubadoras`, formato
  que o regex não reconhecia; a extensão opcional também não estava instalada
  no perfil usado. O padrão forte agora aceita `Meet: <texto>` e o teste RED/GREEN
  cobre o título exato.
- **T-10.H4 (execução de 2026-08-10):** o processo da bandeja agora persiste
  somente `worker_pid`, `worker_iniciado_em`, `worker_terminado_em` e
  `worker_codigo_saida` no JSON atômico do job, e registra os mesmos metadados no
  log sem áudio ou fala. O RED/GREEN de `tests/test_worker_observabilidade.py`
  cobriu lançamento, saída não-zero, preservação do WAV e ausência de texto no
  JSON; o gate dirigido de F10.E permaneceu verde. O atalho oficial do
  Transkriptor foi criado na Startup e a preferência `iniciar_com_windows` foi
  mesclada na configuração. `WhisperFlowLocal.lnk` e `Wispr Flow.lnk` foram
  movidos, sem exclusão, para `Startup/disabled-transcription-apps-2026-08-10`;
  os processos já ativos não foram interrompidos. O gate real de 25 s com fala
  sintética e o gate de 600 s em `--sem-audio` passaram as 11 etapas; o gate
  longo capturou 9.584.000 frames, fechou WAV de 600 s e processou o job em 52 s.
  Uma fala externa do ambiente apareceu no resultado temporário do modo sem
  áudio, sem ser copiada para log ou documentação; isso fica registrado como
  ressalva de loopback, não como detecção espontânea de reunião. Depois dos
  commits, o PID antigo foi encerrado em estado ocioso e o PID 5996 iniciou o
  código atual; a bandeja e o monitor confirmaram startup sem segunda instância.

