# Plano Final — Transkriptor v1.2.1

**Status:** EXECUTADO E VALIDADO  
**Data:** 2026-07-18  
**Método:** SDD + TDD (Superpowers)  
**Escopo:** estabilidade da bandeja, detecção real do Meet e atalho da Área de Trabalho  
**Estimativa:** 6–9h

## 1. Decisão

Será entregue um hotfix pequeno e rastreável sobre a v1.2. O hotfix não trocará o `pystray` nem criará um serviço Windows. Ele corrigirá as duas causas confirmadas e padronizará a criação do atalho.

## 2. Causas confirmadas

| Sintoma | Causa | Evidência |
|---------|-------|-----------|
| Ícone pisca e some | `visible=True` é executado antes de `Icon.run()` criar o `HWND` | processo continua vivo; backend Win32 só cria janela dentro de `_run()` |
| Meet não inicia trabalho | regex termina em `Google Meet$` | título real contém sufixo `- Google Chrome` ou Edge |
| Atalho inconsistente | lógica PowerShell está embutida em uma linha extensa do `.bat` e cria dois atalhos | `instalar.bat` atual |
| Testes não detectam regressão | suíte cobre regex de aba e estado lógico, não lifecycle Win32 | 152 testes verdes com defeito presente |

## 3. Arquitetura aprovada

### 3.1 Bandeja

```text
thread principal
  → cria pystray.Icon (ainda invisível)
  → Icon.run(setup=_ao_bandeja_pronta)
      → backend cria HWND e message loop
      → callback define visible=True
      → inicia monitor uma vez
      → envia toast e registra readiness
```

### 3.2 Detecção

```text
pygetwindow.getAllTitles()
  → titulo_eh_meet(título real)
      → exclusões têm prioridade
      → marcador " - Google Meet"
      → fim do título OU sufixo de navegador
  → debounce 2/3 inalterado
  → _processar_mudanca_meet("iniciou")
  → Transcritor.start()
```

### 3.3 Atalho

```text
resolver_pythonw.py
  → criar_atalho_desktop.ps1 (parâmetros separados)
      → Desktop do usuário via Environment.GetFolderPath
      → Transkriptor.lnk
          target: pythonw.exe
          arguments: transkriptor.pyw
          working directory: BASE_DIR
          icon: transkriptor.ico
```

## 4. Ordem obrigatória

| Fase | Entrega | Gate |
|------|---------|------|
| F0 | baseline + contratos RED | baseline 152 verdes antes do hotfix |
| F1 | bandeja pronta antes de visível | `test_bandeja_lifecycle.py` + mutex |
| F2 | títulos reais + início automático | detector + integração monitor |
| F3 | atalho único e testável | `test_atalho_desktop.py` |
| F4 | regressão completa + manual | estabilidade + all + checklist |

## 5. Alternativas rejeitadas

| Alternativa | Motivo |
|-------------|--------|
| Recriar ícone periodicamente | mascara a ordem incorreta e pode duplicar ícones |
| Watchdog reiniciar o processo | perde estado e não corrige registro Win32 |
| Trocar `pystray` por Qt/WinUI | mudança desproporcional para hotfix |
| Detectar só por URL/título genérico | aumenta falsos positivos e não resolve janela ativa de forma controlada |
| Ativar startup automaticamente | altera preferência do usuário sem autorização |

## 6. Critérios finais

- [x] Ícone aparece uma vez, em até 5s, e permanece 30 minutos.
- [x] Menu abre e estados dinâmicos continuam funcionando.
- [x] Explorer reiniciado não mata o processo e o ícone retorna.
- [x] Chrome e Edge iniciam transcrição após duas confirmações.
- [x] Fechamento do Meet encerra após três ausências.
- [x] Modo manual continua independente do detector.
- [x] Atalho `Transkriptor.lnk` abre via `pythonw.exe` sem console.
- [x] Segunda abertura é bloqueada pelo mutex.
- [x] Preferência de startup permanece inalterada.
- [x] Gate `estabilidade`, suíte completa e gate `all` retornam 0.

## 7. Execução Superpowers

1. Ler este plano, `concept.md`, `spec.md` e `tasks.md`.
2. Executar apenas a primeira tarefa `[ ]`.
3. Invocar `superpowers:test-driven-development` antes de código.
4. Observar RED pelo motivo esperado.
5. Implementar o mínimo e repetir o subset.
6. Se falhar inesperadamente, invocar `superpowers:systematic-debugging`.
7. Antes de marcar a fase concluída, invocar `superpowers:verification-before-completion`.
8. Fazer um commit em português por tarefa.
9. Não publicar antes do gate manual F4.

**Execução:** F0–F4 concluídas. Evidências em `docs/VERIFICACAO.md`. Commits e push permanecem indisponíveis porque este diretório não contém `.git`.
