# Tasks — Transkriptor 1.1

Lista de tarefas acionável derivada da spec e do plan.
Cada tarefa tem ID, fase, arquivo(s) afetados, e critério de aceite.

Convenção de status: `[ ]` pendente, `[~]` em andamento, `[x]` concluído.

---

## Fase 1 — Fundação Estrutural

### T1.1 — Criar config.py
- **Arquivos:** `config.py` (novo)
- **Descrição:** Centralizar todas as constantes da spec seção 5.
- **Critério:** `python -c "import config"` funciona e expõe todas as constantes.

### T1.2 — Refatorar imports para usar config
- **Arquivos:** `transcricao_core.py`, `diarizador.py`, `assistente.py`, `Transkriptor.pyw`
- **Descrição:** Substituir constantes locais por imports de `config`.
- **Critério:** `grep -rn "SAMPLE_RATE\|BASE_DIR\|OLLAMA_URL" *.py *.pyw` só encontra em `config.py`.

### T1.3 — Reescrever transcrever_meet.py como wrapper
- **Arquivos:** `transcrever_meet.py`
- **Descrição:** Remover lógica duplicada; usar `Transcritor` do core.
- **Critério:** Arquivo tem menos de 50 linhas; `python transcrever_meet.py --listar` funciona.

### T1.4 — Remover self._rodando (BUG-01)
- **Arquivos:** `transcricao_core.py:241`
- **Descrição:** Deletar linha `self._rodando = True`.
- **Critério:** `grep "_rodando" *.py` retorna 0 resultados.

---

## Fase 2 — Robustez do Core

### T2.1 — Criar detector_meet.py (BUG-03, BUG-04)
- **Arquivos:** `detector_meet.py` (novo), `Transkriptor.pyw`
- **Descrição:** Regex específico + classe `DetectorMeet` com debounce de N ciclos.
- **Critério:**
  - Título "como usar google meet - Pesquisa Google" retorna `False`.
  - Título "Reunião de equipe - Google Meet" retorna `True`.
  - Precisa de 2 detecções consecutivas para confirmar início.
  - Precisa de 3 ausências consecutivas para confirmar fim.

### T2.2 — Áudio em disco via WAV (BUG-02)
- **Arquivos:** `transcricao_core.py`, `diarizador.py`
- **Descrição:** Substituir `self._audio_completo` (lista em RAM) por arquivo WAV temporário.
- **Critério:**
  - Reunião simulada de 10 min usa menos de 60 MB de RAM.
  - `_diarizado.txt` gerado corretamente lendo do WAV.
  - WAV temporário deletado após diarização.

### T2.3 — Diarização em thread dedicada (BUG-07)
- **Arquivos:** `transcricao_core.py`, `Transkriptor.pyw`
- **Descrição:** `stop()` dispara diarização em thread separada e retorna imediatamente.
- **Critério:**
  - `stop()` retorna em menos de 2s.
  - `transcritor.diarizando == True` durante pós-processamento.
  - Monitor de Meet continua funcionando durante diarização.

### T2.4 — try/finally em _processar (BUG-08)
- **Arquivos:** `transcricao_core.py:125-149`
- **Descrição:** Garantir fechamento de arquivos mesmo com exceção.
- **Critérito:** Simular exceção em `_transcrever_bloco` e verificar que `self._arq` é fechado.

### T2.5 — Normalizar segmentos sobrepostos (BUG-09)
- **Arquivos:** `diarizador.py:79-86`
- **Descrição:** Clamp de segmentos antes de extrair embeddings.
- **Critério:** Segmentos com `start < end_anterior` são ajustados sem erro.

### T2.6 — Criar watchdog.py
- **Arquivos:** `watchdog.py` (novo), `transcricao_core.py`, `Transkriptor.pyw`
- **Descrição:** Thread que verifica saúde das threads críticas a cada 10s.
- **Critério:**
  - Matar `_capturar` manualmente faz watchdog reiniciar em menos de 15s.
  - Após 3 reinícios consecutivos, notifica erro crítico.
  - `Transcritor` expõe `_reiniciar_captura()` e `_reiniciar_processar()`.

### T2.7 — Corrigir porta_livre() (BUG-05)
- **Arquivos:** `assistente.py:477-485`, `Transkriptor.pyw`
- **Descrição:** Lançar `RuntimeError` se nenhuma porta livre; mais portas de fallback.
- **Critério:** Com todas as portas ocupadas, exceção é lançada e usuário é notificado via bandeja.

### T2.8 — Feedback de erro no webbrowser.open (BUG-06)
- **Arquivos:** `Transkriptor.pyw:148-167`
- **Descrição:** Verificar se servidor responde após abrir navegador; notificar se falhar.
- **Critério:** Erro do Flask aparece no status da bandeja e no log com traceback.

---

## Fase 3 — Notificações e Feedback

### T3.1 — Criar notificador.py
- **Arquivos:** `notificador.py` (novo), `requirements.txt`
- **Descrição:** Wrapper sobre `win10toast` com fallback silencioso.
- **Critério:** `notificar("Teste", "Mensagem")` mostra toast; sem win10toast não quebra.

### T3.2 — Ícone dinâmico na bandeja (UX-01)
- **Arquivos:** `Transkriptor.pyw`
- **Descrição:** 4 imagens (azul/verde/dourado/vermelho) trocadas conforme estado.
- **Critério:** Ícone muda de cor visivelmente entre os 4 estados.

### T3.3 — Notificações toast nos eventos (UX-02)
- **Arquivos:** `Transkriptor.pyw`, `transcricao_core.py`
- **Descrição:** Toasts ao iniciar/parar/concluir diarização/erro.
- **Critério:** Toast aparece em cada um dos 4 eventos durante teste.

---

## Fase 4 — UX do Assistente

### T4.1 — Histórico de conversa no backend (UX-04)
- **Arquivos:** `assistente.py` (rota `/api/chat`)
- **Descrição:** Receber `historico` no JSON e incluir no payload do Ollama.
- **Critério:** Payload enviado ao Ollama contém system + histórico + pergunta atual.

### T4.2 — Histórico de conversa no frontend (UX-04)
- **Arquivos:** `assistente.py` (HTML/JS)
- **Descrição:** Array `historico`, truncar em 20, botão "Limpar conversa".
- **Critério:** Follow-up "me detalhe o item 2" funciona após "liste pontos".

### T4.3 — Loading e cancelamento (UX-05)
- **Arquivos:** `assistente.py` (HTML/JS)
- **Descrição:** AbortController, botão Parar, cronômetro, mensagem após 15s.
- **Critério:** Botão Parar cancela streaming; cronômetro mostra tempo decorrido.

### T4.4 — Metadados nas transcrições (UX-03)
- **Arquivos:** `assistente.py` (rota `/api/transcricoes` + frontend)
- **Descrição:** Retornar data/tipo/tamanho/preview; dropdown amigável.
- **Critério:** Dropdown mostra "04/07 18:07 - Olá pessoal..." em vez do nome técnico.

### T4.5 — Acessibilidade (UX-06)
- **Arquivos:** `assistente.py` (HTML/CSS/JS)
- **Descrição:** Contraste AA, focus-visible, ARIA, button em vez de div, labels.
- **Critério:**
  - Lighthouse a11y score maior que 90.
  - Tab navega por todos os interativos.
  - NVDA anuncia novas mensagens no chat.

---

## Fase 5 — Instalação e Startup

### T5.1 — Atualizar requirements.txt (BUG-12)
- **Arquivos:** `requirements.txt`
- **Descrição:** Adicionar torch, torchaudio, win10toast, flask com comentários.
- **Critério:** `pip install -r requirements.txt` (após torch) traz todas as dependências.

### T5.2 — Reescrever instalar.bat
- **Arquivos:** `instalar.bat`
- **Descrição:** 3 passos: torch CUDA, requirements, atalhos.
- **Critério:** Em PC limpo, instalar.bat instala tudo e app funciona.

### T5.3 — Criar atalho de startup (BUG-10)
- **Arquivos:** `instalar.bat` ou `criar_atalhos.ps1`, `Transkriptor.pyw`
- **Descrição:** Atalho em `shell:startup`; item de menu toggle com checkmark.
- **Critério:** Após reiniciar Windows, app aparece na bandeja sozinho.

### T5.4 — Persistir preferência de startup
- **Arquivos:** `Transkriptor.pyw`, `config_user.json` (novo, runtime)
- **Descrição:** Salvar/lêr preferência "iniciar com Windows" em JSON simples.
- **Critério:** Toggle cria/remove atalho e persiste entre reinícios.

---

## Resumo por Arquivo

| Arquivo | Fase | Tarefas |
|---------|------|---------|
| `config.py` (novo) | 1 | T1.1 |
| `transcricao_core.py` | 1, 2 | T1.2, T1.4, T2.2, T2.3, T2.4, T2.6 |
| `diarizador.py` | 1, 2 | T1.2, T2.2, T2.5 |
| `Transkriptor.pyw` | 1, 2, 3, 5 | T1.2, T2.1, T2.3, T2.6, T2.7, T2.8, T3.2, T3.3, T5.3, T5.4 |
| `assistente.py` | 1, 4 | T1.2, T2.7, T4.1, T4.2, T4.3, T4.4, T4.5 |
| `transcrever_meet.py` | 1 | T1.3 |
| `detector_meet.py` (novo) | 2 | T2.1 |
| `watchdog.py` (novo) | 2 | T2.6 |
| `notificador.py` (novo) | 3 | T3.1 |
| `requirements.txt` | 5 | T5.1 |
| `instalar.bat` | 5 | T5.2, T5.3 |

---

## Ordem de Execução

1. T1.1 -> T1.2 -> T1.3 -> T1.4 (Fase 1, sequencial)
2. T2.1, T2.2, T2.3, T2.4, T2.5, T2.6, T2.7, T2.8 (Fase 2, parcialmente paralela)
3. T3.1 -> T3.2, T3.3 (Fase 3, em paralelo com Fase 4)
4. T4.1 -> T4.2 -> T4.3, T4.4, T4.5 (Fase 4, em paralelo com Fase 3)
5. T5.1 -> T5.2 -> T5.3 -> T5.4 (Fase 5, final)

Total: 19 tarefas.
