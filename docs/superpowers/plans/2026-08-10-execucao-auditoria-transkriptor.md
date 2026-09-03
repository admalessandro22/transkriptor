# Execução da auditoria e correção do Transkriptor

> **Para agentes:** executar cada tarefa na ordem, com RED/GREEN e verificação fresca antes de avançar.

**Objetivo:** fechar as lacunas observadas após a validação de produção: tornar o ciclo de pós-processamento auditável sem registrar fala, garantir que resultados `.txt` permaneçam rastreáveis e isolar de forma reversível os gravadores externos que iniciam com o Windows.

**Arquitetura:** o ciclo de captura continua desacoplado do Whisper. O processo da bandeja registra somente metadados seguros de cada worker (ID do job, PID, timestamps e código de saída) em estado durável; o áudio e a transcrição permanecem nos caminhos já validados. Os atalhos de aplicativos externos são movidos para uma pasta de backup dentro da própria inicialização, sem apagar arquivos nem interromper processos ativos.

**Tecnologias:** Python 3.12, pytest, JSON atômico existente em `fila_processamento.py`, Win32/PowerShell somente para a operação reversível de atalhos.

## Restrições globais

- `config.VERSAO` continua sendo a única fonte da versão.
- Nenhuma fala, texto de transcrição ou conteúdo de áudio entra em log, JSON de job ou saída de auditoria.
- Nenhum callback é executado sob `Transcritor._lock`.
- O Flask continua limitado a `127.0.0.1`.
- Cada tarefa de código termina com teste direcionado, suíte relacionada e commit em português.
- O gate real de captura só é repetido com áudio sintético temporário e arquivos fora de `transcricoes/`.

---

### Tarefa 1: Observabilidade durável do worker (T-10.H4)

**Arquivos:**
- Modificar: `fila_processamento.py` para guardar metadados de lançamento/finalização do worker, preservando o esquema seguro do job.
- Modificar: `app_processamento.py` para registrar PID, início, término e código de saída sem conteúdo falado.
- Modificar: `processador_reuniao.py` somente se necessário para manter estados `ready`/`failed` já existentes.
- Testar: `tests/test_worker_observabilidade.py`.

**Interfaces:**
- `FilaProcessamento.registrar_worker(job_id, pid, iniciado_em)` atualiza apenas metadados permitidos.
- `FilaProcessamento.registrar_saida_worker(job_id, codigo, terminado_em)` é idempotente e não muda o estado funcional do job.

- [ ] Escrever testes RED para lançamento e encerramento com código não-zero, verificando que o JSON contém apenas metadados e que o áudio continua preservado.
- [ ] Rodar `python -m pytest tests/test_worker_observabilidade.py -q` e confirmar falha pela ausência da API.
- [ ] Implementar a menor alteração usando a escrita JSON atômica existente e valores serializáveis.
- [ ] Rodar o teste direcionado e o gate da fase F10.E.
- [ ] Fazer commit `fix: torna o worker de transcrição auditável`.

### Tarefa 2: Autostart do Transkriptor e isolamento externo reversível

**Arquivos:**
- Modificar: `config.py`/módulo de configuração apenas se o default de autostart precisar ser explícito.
- Modificar: testes de configuração/startup correspondentes.
- Operar: atalhos exatos em `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`.

- [ ] Escrever teste RED para o default/estado de inicialização esperado, se houver mudança de código.
- [ ] Implementar o default sem alterar chaves desconhecidas e sem criar captura genérica.
- [ ] Validar os destinos e mover somente `WhisperFlowLocal.lnk` e `Wispr Flow.lnk` para uma pasta `disabled-transcription-apps-2026-08-10` dentro da Startup.
- [ ] Confirmar por leitura que os atalhos originais estão no backup e não foram apagados; não encerrar processos ativos.
- [ ] Fazer commit separado apenas se houver alteração de código; a movimentação externa fica registrada como evidência operacional.

### Tarefa 3: Atualização SDD e auditoria de evidências

**Arquivos:**
- Modificar: `docs/sdd/v1.5/tasks.md` com a nova evidência T-10.H4 e a distinção entre validação histórica e estado atual.
- Criar: `docs/sdd/v1.5/auditoria-execucao-2026-08-10.md` com checklist requisito → teste → evidência, sem transcrição ou fala.

- [ ] Registrar o resultado atual do PID único, ícone único, ausência de arquivos em `transcricoes/`, teste de loopback e limitação de Zoom real.
- [ ] Registrar explicitamente a lacuna das duas reuniões históricas: artefatos não estão presentes neste checkout, portanto não serão declarados novamente auditados.
- [ ] Verificar links/caminhos e fazer commit `docs: registra auditoria de execução v1.5`.

### Tarefa 4: Gates de fechamento

- [ ] Rodar `python -m pytest tests/ -q`, `python scripts/verificar_fase.py --fase all`, `python -m compileall -q .` e `git diff --check`.
- [ ] Rodar o gate real curto; se captura tiver sido tocada, rodar também o gate de 600 s em diretório temporário sem fala audível e declarar a limitação.
- [ ] Revalidar processo, memória, CPU, ícones, startup e jobs depois dos gates.
- [ ] Aplicar `verification-before-completion` e reportar somente o que tiver evidência fresca.
