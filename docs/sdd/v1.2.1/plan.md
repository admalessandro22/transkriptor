# Plan — Transkriptor v1.2.1

**Status:** Executado e validado  
**Método:** SDD + TDD (Superpowers)  
**Estimativa:** 6–9h  
**Fonte normativa:** [spec.md](spec.md)

Se qualquer gate falhar: invocar `superpowers:systematic-debugging`, corrigir a causa, repetir o gate e não avançar.

## Fases

| Fase | Objetivo | Estimativa | Requisitos |
|------|----------|------------|------------|
| F0 | Congelar baseline e reproduzir defeitos | 1h | FR-0.* |
| F1 | Corrigir ciclo de vida do ícone e monitor | 2h | FR-1.*, UX-1–3, UX-6 |
| F2 | Detectar títulos reais e integrar início | 2h | FR-2.*, NFR-4 |
| F3 | Criar atalho único e testável | 1–2h | FR-3.*, SEC-3–4, UX-4 |
| F4 | Gate completo, manual e documentação | 1–2h | FR-4.*, NFR-* |

## Dependências

```text
F0 baseline + testes RED
  └─► F1 bandeja pronta
        └─► F2 monitor e Meet real
              └─► F3 atalho
                    └─► F4 gate final
```

Não paralelizar F1 e F2: o monitor só deve iniciar depois do callback de prontidão introduzido em F1.

## F0 — Baseline e reprodução

### Entregáveis

- Baseline registrado: 152 testes verdes antes do hotfix.
- `tests/test_bandeja_lifecycle.py` reproduz visibilidade antecipada.
- Casos reais de Chrome/Edge inicialmente vermelhos em `tests/test_detector_meet.py`.
- `tests/test_integracao_monitor_meet.py` define o contrato detector → app.
- `tests/test_atalho_desktop.py` define metadados do `.lnk`.

### Gate `AC-F0`

O RED deve ser observado individualmente antes de cada implementação. Testes vermelhos não são commitados isoladamente; cada tarefa TDD termina verde.

```powershell
python -m pytest tests/ -v --tb=short -x
```

Baseline esperado antes das mudanças: `152 passed`.

## F1 — Bandeja estável

### Arquitetura

`AppTranskriptor.rodar()` cria `pystray.Icon` e bloqueia na thread principal com `run(setup=self._ao_bandeja_pronta)`. O backend Win32 cria o `HWND`, sinaliza prontidão e só então o callback:

1. define `icon.visible = True`;
2. inicia a ponte Meet quando habilitada;
3. inicia uma única thread `_monitorar_meet`;
4. registra readiness e envia notificações.

Não haverá loop de recriação do ícone. O próprio backend do `pystray` trata `TaskbarCreated` quando o Explorer reinicia.

### Gate `AC-F1`

```powershell
python -m pytest tests/test_bandeja_lifecycle.py tests/test_mutex.py -v --tb=short
```

Critérios:

- nenhum evento `visible=True` antes de `run()` sinalizar prontidão;
- callback de setup inicia o monitor uma vez;
- notificação ocorre após prontidão;
- mutex permanece verde.

## F2 — Detecção real e início automático

### Arquitetura

O detector continuará puro. O regex reconhecerá o marcador ativo ` - Google Meet` quando ele terminar o título ou for seguido por um separador de sufixo de navegador (`-` ou `—`). A lista `_EXCLUIR` continuará prevalecendo.

O tratamento de eventos será extraído para `AppTranskriptor._processar_mudanca_meet(mudanca)`, permitindo testar o fluxo sem executar o `while True`.

### Gate `AC-F2`

```powershell
python -m pytest tests/test_detector_meet.py tests/test_detector_meet_visivel.py tests/test_integracao_monitor_meet.py -v --tb=short
```

Critérios:

- Chrome e Edge positivos;
- pesquisa/tutorial/login negativos;
- 2 ciclos iniciam uma vez;
- 3 ausências encerram uma vez;
- modo manual não é encerrado pelo detector.

## F3 — Atalho confiável

### Arquitetura

Um script PowerShell parametrizado será a única implementação de criação do atalho da Área de Trabalho. `instalar.bat` resolverá `pythonw.exe` e chamará o script com argumentos separados. O teste usará um destino temporário e lerá o `.lnk` de volta via `WScript.Shell`.

### Gate `AC-F3`

```powershell
python -m pytest tests/test_atalho_desktop.py -v --tb=short
```

Critérios:

- um `.lnk` é criado;
- target, arguments, working directory, icon e window style estão corretos;
- caminho com espaços permanece íntegro;
- nenhum atalho de startup é criado pelo script.

## F4 — Verificação e entrega

### Gate automatizado `AC-F4`

```powershell
python scripts/verificar_fase.py --fase estabilidade
python -m pytest tests/ -v --tb=short
python scripts/verificar_fase.py --fase all
```

Todos devem retornar exit code 0.

### Gate manual Windows

1. Encerrar a instância anterior pelo menu.
2. Abrir pelo novo atalho.
3. Confirmar ícone e menu em até 5s.
4. Aguardar 30 minutos ocioso; confirmar processo e ícone ativos.
5. Abrir um Meet no Chrome; confirmar transcrição em até 15s.
6. Minimizar o Meet; com `EXIGIR_JANELA_VISIVEL=False`, confirmar que a reunião continua ativa.
7. Fechar o Meet; confirmar finalização após 3 ciclos.
8. Abrir o atalho duas vezes; confirmar uma única instância.
9. Reiniciar o Explorer pelo Gerenciador de Tarefas; confirmar retorno do ícone.
10. Confirmar que “Iniciar com o Windows” manteve a preferência anterior.

### Rollback

Se o gate manual falhar depois dos testes verdes:

1. não distribuir o hotfix;
2. preservar `transkriptor.log` sem conteúdo de transcrição;
3. restaurar apenas o commit da tarefa causadora;
4. invocar `systematic-debugging` com a evidência do gate;
5. criar novo teste RED e repetir a fase.

## Definição de pronto

A v1.2.1 só pode ser marcada concluída quando `AC-F1` a `AC-F4` estiverem verdes e o checklist manual estiver registrado em `docs/VERIFICACAO.md` com data, versão do Windows, navegador e resultado.
