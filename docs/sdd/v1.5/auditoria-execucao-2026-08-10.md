# Auditoria de execução — Transkriptor v1.5 — 2026-08-10

## Escopo

Esta auditoria fecha a execução operacional do plano v1.5 depois dos hotfixes de
deadlock, detecção, consentimento, captura posterior e COM. Ela não reabre a
captura manual nem declara uma reunião histórica como auditada sem os artefatos
presentes no checkout.

## Evidência atual sem conteúdo sensível

- **Código:** branch `v1.4-deteccao-e-captura`, commit de observabilidade
  `ea32dd6`, versão `config.VERSAO = 1.5.0`.
- **Bandeja:** um `pythonw.exe` executando `transkriptor.pyw` (PID 53676 no
  momento da coleta). O coletor de recursos observou um ícone pystray em todas
  as amostras, crescimento de memória de `0,0 MB` e CPU média de `0,155%` de um
  núcleo em 10 s, dentro dos limites de NFR-10.C2.
- **Reinício pós-commit:** como o PID 53676 ainda carregava o código anterior
  em memória, ele foi encerrado somente quando o log confirmou
  `reunião=False, gravando=False`. O PID 5996 foi iniciado com o commit atual,
  registrou “Bandeja pronta” e “Monitor do Meet iniciado”, e passou uma nova
  amostra de recursos com um ícone, CPU média de `0,471%` e crescimento de
  memória de `0,008 MB`.
- **Fila/saídas:** `transcricoes/` não contém áudio, JSON de job, `.txt` ou
  `.tkpt` no momento desta auditoria. Isso é estado vazio, não prova de que uma
  reunião aceita futura não produzirá resultado; o gate real é obrigatório para
  essa afirmação.
- **Worker:** o JSON atômico continua validando todos os paths dentro de
  `transcricoes/`. O ciclo de worker acrescenta somente PID, instantes e código
  de saída; nenhum campo aceita fala ou conteúdo de transcrição.
- **Inicialização:** `Startup/transkriptor.lnk` aponta para o `pythonw.exe` do
  Python 3.12 e para `C:\Projetos\transkriptor\transkriptor.pyw`, com diretório
  de trabalho do repositório. A preferência `iniciar_com_windows` está `true`.
  Os atalhos `WhisperFlowLocal.lnk` e `Wispr Flow.lnk` estão preservados na
  pasta reversível `Startup/disabled-transcription-apps-2026-08-10`; não foram
  apagados.
- **Processos externos:** os processos já abertos do WhisperFlow/Wispr Flow
  foram apenas identificados e não encerrados para não interromper uma sessão
  ativa. O backup de Startup impede novas inicializações automáticas; o usuário
  pode fechá-los quando não houver ditado em andamento.
- **Gates reais:** o gate de 25 s com fala sintética e o gate de 600 s em
  `--sem-audio` foram aprovados nas 11 etapas. O longo preservou 9.584.000
  frames, fechou um WAV de 600 s e processou o job em 52 s. Mesmo sem áudio
  reproduzido pelo gate, uma fala externa existente no sistema apareceu no
  resultado temporário; o conteúdo não foi copiado nem gravado no log. Isso é
  evidência de que loopback captura sons do sistema quando a captura é
  deliberadamente forçada, não de que o detector abriu uma reunião sozinho.
- **Zoom:** não havia `zoom.exe` em chamada durante a coleta; portanto a
  detecção/consentimento Zoom permanece coberta por testes e ensaio Win32, mas
  não por uma chamada real nesta sessão.

## Matriz de fechamento

| Requisito | Código/teste | Evidência e limite |
|---|---|---|
| FR-10.A1–A4 | `deteccao_reuniao.py`, `tests/test_deteccao_multi_fonte.py` | Microfone isolado não inicia; Meet/Zoom dependem de fonte forte. |
| FR-10.B1–B3 / UX-10.B1–B2 | `aviso_gravacao.py`, `notificador.py`, testes de consentimento/bandeja | Consentimento explícito e canal silencioso; janela Zoom real ainda não foi aberta nesta sessão. |
| FR/NFR-10.C* | `transcricao_core.py`, `captura_leve.py`, watchdog, COM | Gates reais de 25 s e 600 s aprovados; o longo foi silencioso e ainda registrou fala externa do ambiente no resultado temporário. |
| FR-10.D1–D4 / FR-10.E1–E4 | `fila_processamento.py`, `processador_reuniao.py`, `app_processamento.py` | Job atômico, worker separado, `.txt` primário e áudio preservado; observabilidade adicionada em `ea32dd6`. |
| SEC-10.F1–F4 | `config_user.py`, `crypto_storage.py`, fila e fixtures | Merge atômico, paths confinados e testes não tocam o estado real. |
| FR-10.G1–G3 | `recuperacao_audio.py`, `tests/test_recuperacao_audio.py` | Evidência histórica de 2026-08-06 permanece em `recuperacao-2026-08-06.md`; os arquivos não estão neste checkout atual. |
| NFR-10.H1–H4 | `tests/test_worker_observabilidade.py`, `scripts/verificar_fase.py` | Suíte/gates finais são a condição de fechamento; não declarar reunião real sem saída `.txt` observada. |

## Lacunas que permanecem declaradas

1. As duas reuniões históricas de 2026-08-06 não estão presentes em
   `transcricoes/` nesta execução. Não há base para revisar novamente a
   degravação palavra a palavra sem restaurar os WAVs/TXTs preservados.
2. Não houve chamada Zoom real disponível durante esta coleta.
3. Os processos externos existentes continuam vivos até serem fechados de forma
   consciente; o isolamento aplicado é de inicialização e é reversível.

## Rollback operacional

Para reverter apenas o isolamento externo, mova os dois `.lnk` da pasta
`disabled-transcription-apps-2026-08-10` de volta para a raiz de `Startup`. Para
reverter código, use `git revert ea32dd6`; os JSONs e áudios de jobs não são
apagados.
