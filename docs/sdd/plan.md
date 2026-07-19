# Plan — Transkriptor 1.1

Plano de implementação em 5 fases. Cada fase é independente e testável.
As fases são ordenadas por dependência: a base estrutural vem antes das
melhorias de UX que dependem dela.

---

## Visão Geral

| Fase | Foco | Duração estimada | Entregável |
|------|------|-------------------|------------|
| 1 | Fundação estrutural | 2-3h | config.py + refatoração de imports + CLI wrapper |
| 2 | Robustez do core | 3-4h | Áudio em disco + debounce + watchdog + try/finally |
| 3 | Notificações e feedback | 1-2h | notificador.py + ícone dinâmico + toasts |
| 4 | UX do assistente | 2-3h | Histórico de conversa + loading + metadados + a11y |
| 5 | Instalação e startup | 1h | requirements + instalar.bat + shell:startup |

Total estimado: 9-13h de implementação.

---

## Fase 1 — Fundação Estrutural

**Objetivo:** Centralizar configurações, eliminar código duplicado, preparar
a base para as correções das fases seguintes.

### Por que primeiro
Todas as outras fases referenciam constantes e módulos. Se não centralizar
primeiro, as correções espalham magic numbers novamente. E o CLI duplicado
gera confusão sobre qual caminho de código está sendo usado.

### Passos

1. **Criar `config.py`** com todas as constantes listadas na spec (seção 5).
   - Importar em todos os módulos que definem constantes locais.
   - Remover definições duplicadas de `SAMPLE_RATE`, `BASE_DIR`, etc.

2. **Reescrever `transcrever_meet.py`** como wrapper sobre `Transcritor`:
   - Manter argparse (interface de CLI não muda).
   - Instanciar `Transcritor`, chamar `start()`, aguardar `KeyboardInterrupt`,
     chamar `stop()`.
   - Remover funções `capturar()`, `transcrever()`, `processar_bloco()`.
   - Meta: <50 linhas.

3. **Remover `self._rodando`** em `transcricao_core.py` (BUG-01).
   - Uma linha. Verificar que nada referencia `_rodando` (apenas `rodando`).

4. **Mover constantes** de `diarizador.py` e `assistente.py` para `config.py`:
   - `LIMIAR_COSSENO`, `DURACAO_MIN_SEG`, `OLLAMA_URL`, `PORTA_ASSISTENTE`.
   - Importar de `config`.

### Validação
- `python -c "import config"` funciona.
- `python transcrever_meet.py --listar` funciona (usa config indiretamente).
- `python transcrever_meet.py --chunk 3` transcreve por 10s e salva .txt.
- `grep -r "_rodando" *.py` retorna 0 resultados.
- `transcrever_meet.py` tem menos de 50 linhas.

---

## Fase 2 — Robustez do Core

**Objetivo:** Corrigir os bugs de engenharia que causam vazamento de memória,
bloqueio de threads, arquivos abertos, e detecção frágil.

### Por que segundo
Depende do `config.py` da Fase 1 para constantes de intervalo e limiares.
As correções aqui mudam a estrutura interna do `Transcritor`, então devem
acontecer antes das melhorias de UX que interagem com o core.

### Passos

1. **Criar `detector_meet.py`** (BUG-03 + BUG-04):
   - Função `titulo_eh_meet(titulo)` com regex específico.
   - Classe `DetectorMeet` com método `verificar()` que retorna `True/False`.
   - Contadores de confirmação (`_confirma_inicio`, `_confirma_fim`).
   - `verificar()` só retorna `True` após N confirmações (config).
   - Exclusões: títulos com "pesquisa", "search", "como usar".
   - `Transkriptor.pyw` usa `DetectorMeet` em vez da função inline.

2. **Áudio em disco** (BUG-02):
   - Em `Transcritor.__init__`: preparar caminho do WAV temporário.
   - Em `_abrir_arquivo()`: também abrir `self._wav` com `wave.open()`.
   - Em `_transcrever_bloco()`: substituir `self._audio_completo.append()` por
     `self._wav.writeframes()`.
   - Em `_rodar_diarizacao()`: ler trechos do WAV via `setpos` + `readframes`
     em vez de `np.concatenate(self._audio_completo)`.
   - Em `stop()` ou `_rodar_diarizacao()` (após gerar diarizado): deletar WAV.
   - Remover `self._audio_completo` completamente.
   - Manter `self._segmentos` (timestamps + texto — leve, sem áudio).

3. **Diarização em thread dedicada** (BUG-07):
   - Em `stop()`: após fechar arquivos, lançar
     `threading.Thread(target=self._rodar_diarizacao, daemon=True).start()`.
   - `stop()` retorna imediatamente.
   - Adicionar `self.diarizando = False` (set True no início da thread,
     False no fim).
   - `Transkriptor.pyw` verifica `transcritor.diarizando` para o status.

4. **try/finally em `_processar`** (BUG-08):
   - Envolver corpo em `try:`, adicionar `finally:` que fecha `self._arq`
     e `self._wav`, e seta `self.rodando = False`.

5. **Segmentos sobrepostos na diarização** (BUG-09):
   - Em `diarizador.py`, antes do loop de extração:
     normalizar segmentos com `start = max(start, end_anterior)`.
   - Clamp de índices: `i_start = max(0, ...)`, `i_end = min(len(audio), ...)`.
   - Pular se `i_start >= i_end`.

6. **Criar `watchdog.py`**:
   - Classe `Watchdog` com `start()`, `stop()`, `_loop()`, `_verificar()`.
   - Verifica threads do `Transcritor` a cada `INTERVALO_WATCHDOG` segundos.
   - Reinicia thread morta (chama método de reinício no `Transcritor`).
   - Limite de `LIMITE_REINICIOS` (3) reinícios consecutivos.
   - `Transcritor` precisa expor `_reiniciar_captura()` e `_reiniciar_processar()`.
   - `Transkriptor.pyw` instancia e inicia `Watchdog` no `rodar()`.

7. **Corrigir `porta_livre()`** (BUG-05):
   - Retornar exceção `RuntimeError("Nenhuma porta livre")` se todas ocupadas.
   - Adicionar portas 5070, 5080, 5090, 5100 ao fallback.
   - `_iniciar_assistente()` em `Transkriptor.pyw` captura e notifica.

### Validação
- Reunião simulada de 10 min não ultrapassa 60 MB de RAM.
- `_diarizado.txt` gerado corretamente a partir do WAV.
- Durante diarização, o status da bandeja mostra "Separando vozes" e o
  monitor continua detectando (simular abertura de Meet durante diarização).
- Matar `_capturar` manualmente faz watchdog reiniciar em menos de 15s.
- Segmentos sobrepostos não causam erro (teste com segmentos mock).
- `porta_livre()` com todas as portas ocupadas lança exceção.

---

## Fase 3 — Notificações e Feedback

**Objetivo:** Dar visibilidade ao usuário sobre o que o app está fazendo.

### Por que terceiro
Depende do `watchdog.py` e do `detector_meet.py` para saber quando notificar.
Depende do `config.py` para mensagens e constantes.

### Passos

1. **Instalar `win10toast`** e adicionar a `requirements.txt`.

2. **Criar `notificador.py`**:
   - Função `notificar(titulo, mensagem, icone=None)`.
   - Wrapper sobre `win10toast.ToastNotifier`.
   - Cache do notifier (criar uma vez, reutilizar).
   - Fallback silencioso se win10toast não estiver disponível (log only).

3. **Ícone dinâmico na bandeja** (UX-01):
   - Em `Transkriptor.pyw`, gerar 4 imagens com `criar_imagem()`:
     - `img_aguardando` (azul escuro)
     - `img_transcrevendo` (verde)
     - `img_diarizando` (dourado)
     - `img_erro` (vermelho)
   - Em `_atualizar_tooltip()`, além de mudar o `title`, mudar `self.icone.icon`.
   - Para o "pulso" verde durante transcrição: thread que alterna
     `img_transcrevendo` / `img_aguardando` a cada 2s (opcional, se pystray
     suportar troca dinâmica sem reiniciar o icon).

4. **Notificações toast** (UX-02):
   - Ao iniciar transcrição: `notificar("Transkriptor", "Transcrição iniciada")`.
   - Ao salvar: `notificar("Transkriptor", f"Salvo: {nome_arquivo}")`.
   - Ao concluir diarização: `notificar("Transkriptor", f"Vozes separadas: {nome}")`.
   - Ao erro: `notificar("Transkriptor", f"Erro: {msg}")`.
   - Chamar `notificar()` nos pontos apropriados de `Transkriptor.pyw`.

### Validação
- Toast aparece ao iniciar/parar transcrição (testar com Meet simulado).
- Ícone muda de cor: aguardando (azul) transcrevendo (verde) diarizando (dourado).
- Se `win10toast` não instalado, app não quebra (fallback).

---

## Fase 4 — UX do Assistente

**Objetivo:** Corrigir os problemas de UX da página web do assistente.

### Por que quarto
Independente das fases 2-3 na lógica, mas aproveita o `config.py` para
`MAX_HISTORICO_CHAT`. Pode ser feita em paralelo com a Fase 3.

### Passos

1. **Histórico de conversa** (UX-04):
   - Backend: `/api/chat` recebe `historico` no JSON e inclui no payload do Ollama.
   - Frontend: manter array `historico = []`.
   - Ao enviar pergunta: adicionar `{"role":"user","content":pergunta}` ao array.
   - Ao receber resposta completa: adicionar `{"role":"assistant","content":resposta}`.
   - Truncar para `MAX_HISTORICO_CHAT` (20) mensagens mais recentes.
   - Botão "Limpar conversa" que zera `historico` e recarrega o empty state.

2. **Loading e cancelamento** (UX-05):
   - Adicionar `AbortController` no JS para poder cancelar o `fetch`.
   - Botão "Parar" aparece durante streaming, no lugar do botão enviar.
   - Cronômetro: `setInterval` atualiza "Processando... Ns" a cada segundo.
   - Após 15s sem primeiro token: mudar mensagem para "O modelo está pensando...".
   - Limpar interval ao receber primeiro token ou ao cancelar.

3. **Metadados nas transcrições** (UX-03):
   - `/api/transcricoes` retorna JSON com `arquivo`, `data`, `tipo`,
     `tamanho_kb`, `preview` (primeiros 80 caracteres do conteúdo).
   - Frontend: dropdown mostra `"04/07 18:07 - Olá pessoal, bom dia..."`.
   - Badge "com vozes" para arquivos `_diarizado.txt`.

4. **Acessibilidade** (UX-06):
   - Contraste: `--text-3` para `#807a73`, `--border` para `rgba(255,255,255,0.10)`.
   - Action-cards: `<div>` para `<button>` com `aria-label`.
   - Labels associadas aos selects (`<label for>`).
   - Chat: `role="log"` + `aria-live="polite"`.
   - `:focus-visible` com `outline: 2px solid var(--gold-bright)`.
   - Navegação por setas nos action-cards (JS).
   - Foco automático no textarea ao carregar.
   - Substituir `alert()` por toast inline no chat.

### Validação
- Perguntar "liste pontos", depois "me detalhe o item 2" funciona (contexto mantido).
- Botão "Parar" cancela o streaming e mostra texto parcial recebido.
- Cronômetro aparece e para ao receber resposta.
- Dropdown mostra data + preview em vez de nome técnico.
- Contraste validado com axe DevTools ou Lighthouse (score a11y >90).
- Tab navega por todos os elementos interativos na ordem esperada.
- Leitor de tela (NVDA) anuncia novas mensagens no chat.

---

## Fase 5 — Instalação e Startup

**Objetivo:** Garantir que o app instale todas as dependências corretamente
e inicie automaticamente com o Windows.

### Por que por último
Depende de todos os módulos estarem criados e importando corretamente.
O `requirements.txt` final só pode ser congelado depois que todos os
módulos (incluindo `win10toast`) existirem e forem importados.

### Passos

1. **Atualizar `requirements.txt`** (BUG-12):
   - Adicionar `torch>=2.0`, `torchaudio>=2.0` com comentário sobre index CUDA.
   - Adicionar `win10toast>=0.0`.
   - Adicionar `flask>=3.0`.
   - Pin de versões apenas onde necessário (faster-whisper, soundcard, pystray).

2. **Reescrever `instalar.bat`**:
   - Passo 1: instalar torch/torchaudio com index CUDA.
   - Passo 2: `pip install -r requirements.txt`.
   - Passo 3: criar atalho no desktop e (opcional) no startup.
   - Mensagens em português, com verificacao de sucesso de cada passo.

3. **Criar `criar_atalhos.ps1`** (ou embutir no instalar.bat):
   - Atalho desktop: "Transkriptor 1.0.lnk" (já existe, recriar).
   - Atalho startup: `shell:startup` (BUG-10).
   - Ambos apontam para `pythonw.exe Transkriptor.pyw`.

4. **Item de menu "Iniciar com o Windows"** (BUG-10):
   - Em `Transkriptor.pyw`, adicionar item toggle com checkmark.
   - Verifica se o atalho de startup existe para definir o estado inicial.
   - Ao ativar: cria atalho em `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`.
   - Ao desativar: remove o atalho.
   - Persistir a preferência (arquivo `config_user.json` simples).

### Validação
- `instalar.bat` em PC limpo instala tudo e o app funciona.
- Após reiniciar o Windows, o app aparece na bandeja sozinho.
- Toggle "Iniciar com o Windows" cria/remove o atalho corretamente.
- `pip install -r requirements.txt` traz todas as dependências (exceto torch
  que precisa do index CUDA — documentado no instalar.bat).

---

## Ordem de Execução Recomendada

```
Fase 1 (fundação)
    |
    v
Fase 2 (robustez do core)
    |
    +---> Fase 3 (notificacoes)  --+
    |                              |
    +---> Fase 4 (UX assistente) --+
                                   |
                                   v
                            Fase 5 (instalacao)
```

Fases 3 e 4 podem ser feitas em paralelo após a Fase 2.
Fase 5 deve ser a última porque consolida todas as dependências.

---

## Gestão de Risco

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| `win10toast` não funciona no Windows 11 | Media | Baixo | Fallback para log only; avaliar `plyer` como alternativa |
| pystray não suporta troca dinâmica de ícone | Media | Baixo | Recriar o `Icon` a cada mudança de estado (testar performance) |
| WAV temporário cresce demais em disco | Baixa | Medio | Limpar WAVs antigos no startup; limitar a 500MB por reunião |
| Torch CUDA incompatible com GPU do usuario | Baixa | Medio | Fallback para CPU (`device="cpu"`) ja implementado |
| Ollama nao rodando quando usuario abre assistente | Alta | Baixo | Ja tratado (status offline no UI); adicionar instrucoes de como iniciar |
| Monitor de janelas (pygetwindow) falha em multi-monitor | Baixa | Medio | Catch de exceção por janela; logar e continuar |

