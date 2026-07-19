# Spec — Transkriptor v1.2.1

Especificação normativa do hotfix de estabilidade da bandeja, detecção real do Google Meet e atalho da Área de Trabalho.

**Convenção:** `FR-*` funcional · `NFR-*` não funcional · `SEC-*` segurança · `UX-*` experiência · `AC-*` aceite.

## 1. Requisitos funcionais

### Fase 0 — Contrato e reprodução

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-0.1 | Criar teste de regressão que demonstre que `visible=True` não pode ocorrer antes de o callback `setup` de `Icon.run()` | P0 |
| FR-0.2 | Adicionar títulos reais de Chrome e Edge à matriz de testes do detector | P0 |
| FR-0.3 | Preservar baseline dos 152 testes existentes antes da primeira correção | P0 |
| FR-0.4 | Registrar o novo subset no gate `scripts/verificar_fase.py --fase estabilidade` | P1 |

### Fase 1 — Ciclo de vida da bandeja

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-1.1 | `AppTranskriptor.rodar()` deve chamar `Icon.run(setup=...)` na thread principal | P0 |
| FR-1.2 | O callback de setup deve definir `icon.visible=True` somente depois que o backend sinalizar prontidão | P0 |
| FR-1.3 | A thread `_monitorar_meet` deve iniciar no callback de setup, uma única vez | P0 |
| FR-1.4 | Toasts e `Icon.notify()` de inicialização devem ocorrer somente após a bandeja estar pronta | P1 |
| FR-1.5 | O log deve registrar `Bandeja pronta` e `Monitor do Meet iniciado`, sem títulos de janelas | P1 |
| FR-1.6 | Falha ao preparar a bandeja deve ser registrada com stack trace e encerrar o processo com mensagem fatal, em vez de deixá-lo invisível | P0 |
| FR-1.7 | O mutex existente deve continuar impedindo uma segunda instância | P0 |
| FR-1.8 | Um lock cujo PID já terminou deve ser considerado obsoleto mesmo enquanto o kernel ainda aceitar `OpenProcess` para esse PID | P0 |
| FR-1.9 | O startup da bandeja não deve importar `transcricao_core`/Whisper antes de uma transcrição ser solicitada | P0 |

### Fase 2 — Detecção real do Google Meet

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-2.1 | Reconhecer `Daily - Google Meet - Google Chrome` | P0 |
| FR-2.2 | Reconhecer títulos com sufixo do Microsoft Edge, inclusive separador `—` e perfil do navegador | P0 |
| FR-2.3 | Continuar reconhecendo `Daily - Google Meet` e `meet.google.com/abc-defg-hij` | P0 |
| FR-2.4 | Continuar rejeitando busca, ajuda, tutorial, login e títulos que apenas mencionam Google Meet | P0 |
| FR-2.5 | Preservar debounce padrão: 2 presenças para iniciar e 3 ausências para encerrar | P0 |
| FR-2.6 | Extrair o tratamento da mudança `iniciou/encerrou` para método testável sem executar o loop infinito | P1 |
| FR-2.7 | Quando o detector retornar `iniciou`, o app deve chamar `_iniciar_transcricao()` exatamente uma vez | P0 |
| FR-2.8 | Exceções de enumeração de janelas não podem encerrar a thread do monitor e não podem logar os títulos coletados | P1 |

### Fase 3 — Atalho da Área de Trabalho

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-3.1 | Criar um único atalho `Transkriptor.lnk` na pasta retornada por `[Environment]::GetFolderPath('Desktop')` | P0 |
| FR-3.2 | O alvo do atalho deve ser o `pythonw.exe` resolvido por `scripts/resolver_pythonw.py` | P0 |
| FR-3.3 | Os argumentos devem apontar para `transkriptor.pyw`, com aspas válidas para caminhos com espaços | P0 |
| FR-3.4 | `WorkingDirectory`, `IconLocation`, descrição e `WindowStyle=7` devem ser preenchidos | P1 |
| FR-3.5 | O script deve aceitar destino alternativo para teste automatizado sem escrever na Área de Trabalho real | P0 |
| FR-3.6 | `instalar.bat` deve usar o script único de criação de atalho e falhar claramente se ele não for criado | P1 |
| FR-3.7 | A criação do atalho não deve alterar `iniciar_com_windows` nem criar um segundo atalho redundante | P0 |

### Fase 4 — Gate e entrega

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-4.1 | O gate `estabilidade` deve executar testes da bandeja, detector, integração do monitor e atalho | P0 |
| FR-4.2 | Criar checklist manual reproduzível para bandeja, Meet, mutex, Explorer e atalho | P0 |
| FR-4.3 | Executar suíte completa e `verificar_fase.py --fase all` sem regressão | P0 |
| FR-4.4 | Atualizar manual e changelog somente depois dos gates verde | P1 |

## 2. Requisitos não funcionais

| ID | Requisito |
|----|-----------|
| NFR-1 | Compatibilidade Windows 10/11 e Python 3.12+ |
| NFR-2 | Ícone utilizável em até 5 segundos depois de iniciar `pythonw.exe`, excluído tempo de instalação |
| NFR-3 | Processo e ícone permanecem ativos por pelo menos 30 minutos ociosos no gate manual |
| NFR-4 | Meet reconhecido e transcrição solicitada em até 15 segundos com intervalo de 5s e confirmação 2 |
| NFR-5 | Nenhuma nova dependência Python de runtime |
| NFR-6 | Uma única thread de monitoramento por processo |
| NFR-7 | Todos os testes existentes permanecem verdes; cobertura nova inclui os três defeitos relatados |

## 3. Segurança

| ID | Requisito |
|----|-----------|
| SEC-1 | Flask continua restrito a `127.0.0.1`; este hotfix não altera bind ou token |
| SEC-2 | Não registrar títulos completos de janelas, transcrições, prompts ou áudio |
| SEC-3 | Argumentos PowerShell devem ser enviados como parâmetros, sem interpolar dados do usuário em código executável |
| SEC-4 | O atalho deve apontar somente para caminhos absolutos resolvidos dentro da instalação e para o interpretador local validado |
| SEC-5 | O hotfix não pode remover ou contornar o mutex de instância única |

## 4. UX

| ID | Requisito |
|----|-----------|
| UX-1 | O ícone não deve piscar e desaparecer durante uma inicialização normal |
| UX-2 | O toast “Transkriptor ativo” só aparece quando o menu já pode ser aberto |
| UX-3 | O tooltip inicial deve informar “Aguardando Meet” |
| UX-4 | O atalho deve se chamar `Transkriptor` e usar `transkriptor.ico` |
| UX-5 | Uma segunda abertura deve informar que o app já está na bandeja, sem criar outro ícone persistente |
| UX-6 | Erro fatal de bandeja deve mostrar caminho do log e não deixar processo órfão invisível |

## 5. Critérios de aceite globais

- [x] `python -m pytest tests/test_bandeja_lifecycle.py -v` passa.
- [x] `python -m pytest tests/test_detector_meet.py tests/test_integracao_monitor_meet.py -v` passa.
- [x] `python -m pytest tests/test_atalho_desktop.py -v` passa usando pasta temporária.
- [x] `python scripts/verificar_fase.py --fase estabilidade` retorna 0.
- [x] `python -m pytest tests/ -v --tb=short` retorna 0.
- [x] `python scripts/verificar_fase.py --fase all` retorna 0.
- [x] Em execução real, o ícone fica acessível por 30 minutos sem desaparecer.
- [x] Reiniciar o Explorer não encerra o app; o ícone volta a ser registrado pelo backend do `pystray`.
- [x] `Daily - Google Meet - Google Chrome` inicia a transcrição depois de duas leituras.
- [x] O atalho real abre uma única instância sem janela de console.

## 6. Rastreabilidade

```text
concept.md
  → spec.md (FR/NFR/SEC/UX)
    → plan.md (F0–F4 + gates)
      → tasks.md (T-F*-*)
        → docs/superpowers/plans/2026-07-18-transkriptor-v1.2.1-tray-stability.md
```
