# Spec — Transkriptor 1.1

Especificação técnica detalhada para correção de todos os pontos apontados
na revisão de engenharia sênior e análise UX.

---

## 1. Estrutura de Arquivos (Refatoração)

```
trancricaoreunioes/
├── Transkriptor.pyw          # Entry point: bandeja + monitor + watchdog
├── transcricao_core.py      # Classe Transcritor (captura + whisper + áudio em disco)
├── diarizador.py            # Diarização (embeddings + clustering)
├── assistente.py            # Servidor Flask + página web + histórico de conversa
├── notificador.py           # Notificações nativas do Windows (toasts)
├── detector_meet.py         # Detecção robusta de Google Meet com debounce
├── watchdog.py              # Monitor de threads críticas + reinicia se morrer
├── config.py                # Configurações centralizadas (modelo, idioma, portas)
├── transcrever_meet.py      # CLI — wrapper fino sobre Transcritor (sem lógica duplicada)
├── Transkriptor.ico
├── Transkriptor.log
├── requirements.txt         # Inclui torch/torchaudio com instruções de index CUDA
├── iniciar.bat
├── instalar.bat
├── transcricoes/            # Saída .txt e .txt_diarizado
└── docs/sdd/                # Estes artefatos
```

### Novos módulos
- `config.py` — constantes e configurações centralizadas (evita magic numbers espalhados)
- `notificador.py` — wrapper sobre `win10toast` ou `plyer` para notificações nativas
- `detector_meet.py` — lógica de detecção isolada e testável
- `watchdog.py` — thread que verifica saúde das threads críticas

### Removidos
- Nenhum arquivo é removido, mas `transcrever_meet.py` é reescrito como wrapper de 30 linhas

---

## 2. Correções de Engenharia

### 2.1 Variável fantasma `self._rodando` (BUG-01)

**Arquivo:** `transcricao_core.py:241`
**Problema:** `self._rodando = True` cria atributo nunca lido; `self.rodando` é o correto.
**Correção:** Remover a linha `self._rodando = True`. Manter apenas `self.rodando = True`.

### 2.2 Vazamento de memória em áudio acumulado (BUG-02)

**Arquivo:** `transcricao_core.py:56`
**Problema:** `self._audio_completo` acumula todo o áudio em RAM. Reunião de 1h = ~230 MB; 3h = ~690 MB.
**Correção:**
- Substituir a lista em memória por um arquivo WAV temporário em disco.
- Usar o módulo `wave` da stdlib (sem dependência extra) para escrever chunks de áudio no arquivo `_tmp_audio.wav` na pasta de transcrições.
- A cada bloco transcrito, escrever o chunk no WAV com `wave.writeframes()`.
- Na diarização, abrir o WAV com `wave.open()` e ler apenas os trechos necessários por offset (seek via `setpos`).
- Deletar o WAV temporário após a diarização (ou após gerar o `_diarizado.txt`).
- Se a diarização estiver desativada, deletar o WAV ao final do `stop()`.
- Meta de RAM: <50 MB independente da duração da reunião.

**Detalhe técnico:**
```python
import wave, struct
# Na inicialização:
self._wav = wave.open(caminho_wav, "wb")
self._wav.setnchannels(1)
self._wav.setsampwidth(2)  # int16
self._wav.setframerate(SAMPLE_RATE)
# A cada bloco:
self._wav.writeframes((audio * 32767).astype(np.int16).tobytes())
# Na leitura para diarização:
self._wav.setpos(int(start * SAMPLE_RATE))
frames = self._wav.readframes(int((end - start) * SAMPLE_RATE))
trecho = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
```

### 2.3 Detecção de Meet frágil com falso-positivos (BUG-03)

**Arquivo:** novo `detector_meet.py`
**Problema:** `"google meet" in t.lower()` dispara em buscas, abas de ajuda, etc.
**Correção:**
- Padrão de título do Meet ativo: `"<nome da sala> - Google Meet"` ou `"Meet - <codigo>"`.
- Regex específico: `r"[\w\s-]+ - Google Meet$"` (título termina com " - Google Meet").
- Também aceitar: `"meet.google.com/"` no título (quando ainda carregando).
- Excluir títulos que contenham: "pesquisa", "search", "google search", "como usar".
- Verificar que a janela correspondente está visível e focada (não minimizada).

### 2.4 Sem debounce no monitor de Meet (BUG-04)

**Arquivo:** `Transkriptor.pyw` (ou `detector_meet.py`)
**Problema:** Oscilação start/stop quando o título pisca durante o carregamento.
**Correção:**
- Implementar contador de confirmação: o Meet só é considerado "iniciado" após ser detectado por **N ciclos consecutivos** (N=2, ou seja, ~10s).
- O Meet só é considerado "encerrado" após **N ciclos consecutivos sem detecção** (N=3, ou seja, ~15s — evita parar por um glitch momentâneo).
- Variáveis de estado: `_meet_confirmado_inicio` (int), `_meet_confirmado_fim` (int).

### 2.5 Flask `porta_livre()` retorna 0 (BUG-05)

**Arquivo:** `assistente.py:477`
**Problema:** Se todas as portas estiverem ocupadas, retorna 0 e o navegador abre URL inválida.
**Correção:**
- Se `porta_livre()` retornar 0, lançar exceção explícita com mensagem útil.
- O chamador (`Transkriptor.pyw`) captura e notifica o usuário via status da bandeja.
- Adicionar mais portas de fallback: 5070, 5080, 5090, 5100.

### 2.6 Sem feedback de erro no `webbrowser.open` (BUG-06)

**Arquivo:** `Transkriptor.pyw:148`
**Problema:** Se o navegador não abrir ou o Flask morrer, sem feedback.
**Correção:**
- Após `webbrowser.open()`, esperar 2s e verificar se o servidor responde (`urllib.request.urlopen` com timeout curto).
- Se não responder, notificar via status da bandeja: "Erro ao abrir assistente. Verifique o log."
- Registrar erro no log com traceback completo.

### 2.7 `stop()` bloqueia diarização na thread chamadora (BUG-07)

**Arquivo:** `transcricao_core.py:262`
**Problema:** Diarização pode levar minutos, bloqueando o monitor de Meet.
**Correção:**
- `stop()` sinaliza parada, fecha o arquivo de texto, e **dispara a diarização em uma thread dedicada** (`threading.Thread(target=self._rodar_diarizacao, daemon=True)`).
- `stop()` retorna imediatamente após fechar o arquivo de texto.
- A thread de diarização atualiza o status via `on_status` quando terminar.
- O `Transcritor` expõe `diarizando` (bool) para o estado de pós-processamento.
- Se uma nova transcrição começar enquanto a diarização anterior roda, ela continua em background sem bloquear.

### 2.8 Arquivo não fecha se `_processar` morrer (BUG-08)

**Arquivo:** `transcricao_core.py:143`
**Problema:** Exceção não capturada em `_processar` deixa `self._arq` aberto.
**Correção:**
- Envolver o corpo de `_processar` em `try/finally`.
- No `finally`: escrever linha de encerramento, fechar `self._arq`, fechar `self._wav` se existir, e setar `self.rodando = False`.
- Garantir que mesmo com exceção, os arquivos sejam fechados e o estado seja limpo.

### 2.9 Diarização com segmentos sobrepostos (BUG-09)

**Arquivo:** `diarizador.py:79`
**Problema:** Segmentos sobrepostos extraem áudio duplicado, distorcendo embeddings.
**Correção:**
- Antes de extrair embeddings, normalizar os segmentos: se `start < end_do_segmento_anterior`, ajustar `start = max(start, end_anterior)`.
- Se após o ajuste `start >= end`, pular o segmento (duração zero).
- Garantir que `i_start < i_end` e ambos dentro dos limites do array de áudio.
- Clamp: `i_start = max(0, i_start)`, `i_end = min(len(audio), i_end)`.

### 2.10 Sem inicialização com o Windows (BUG-10)

**Arquivo:** `Transkriptor.pyw` + `instalar.bat`
**Problema:** App não volta após reiniciar o PC.
**Correção:**
- No `instalar.bat`, criar atalho em `shell:startup`:
  `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Transkriptor.lnk`
- O atalho aponta para `pythonw.exe Transkriptor.pyw` com WorkingDirectory correto.
- Adicionar item de menu na bandeja: "Iniciar com o Windows" (toggle, com checkmark via `pystray.MenuItem(checked=lambda i: ...)`).
- O toggle cria/remove o atalho de startup dinamicamente.

### 2.11 `transcrever_meet.py` duplica lógica (BUG-11)

**Arquivo:** `transcrever_meet.py`
**Problema:** CLI mantém cópia de captura+transcrição+loop, divergindo do core.
**Correção:**
- Reescrever como wrapper de ~40 linhas:
  - Parse de argumentos (argparse) permanece.
  - Instanciar `Transcritor(modelo=..., idioma=..., pasta_saida=..., diarizar_ao_final=False)`.
  - Chamar `start()`, aguardar `KeyboardInterrupt`, chamar `stop()`.
  - Sem lógica de captura, thread, ou transcrição duplicada.

### 2.12 Sem torch/torchaudio no requirements (BUG-12)

**Arquivo:** `requirements.txt` + `instalar.bat`
**Problema:** `pip install -r requirements.txt` não traz torch; diarização quebra.
**Correção:**
- `requirements.txt` incluir `torch>=2.0` e `torchaudio>=2.0` (sem pin de versão exata para compatibilidade de CUDA).
- `instalar.bat` instalar torch/torchaudio com o index CUDA apropriado **antes** do `pip install -r requirements.txt`:
  ```bat
  python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
  python -m pip install -r requirements.txt
  ```
- Adicionar comentário no `requirements.txt` explicando a instalação do torch.

---

## 3. Correções de UX

### 3.1 Sem feedback de transcrição ao vivo (UX-01)

**Problema:** Durante a reunião, usuário não vê o que está sendo transcrito.
**Correção:**
- No `Transkriptor.pyw`, adicionar ícone dinâmico na bandeja:
  - Aguardando: círculo azul escuro.
  - Transcrevendo: círculo verde com pulso (gerar duas imagens e alternar a cada 2s, ou usar cor diferente).
  - Diarizando: círculo dourado.
  - Erro: círculo vermelho.
- A cada bloco transcrito com texto, mostrar uma **notificação toast** com os primeiros 60 caracteres seguidos de "..." (apenas se a janela do Meet não estiver focada, para não atrapalhar).
- Implementar em `notificador.py`.

### 3.2 Sem confirmação de início/fim (UX-02)

**Problema:** Usuário não sabe se está gravando.
**Correção:**
- Notificação toast ao iniciar transcrição: "🎙 Transkriptor — Transcrição iniciada (reunião detectada)".
- Notificação toast ao finalizar: "✅ Transkriptor — Transcrição salva: transcricao_HHhMM.txt".
- Notificação toast ao concluir diarização: "👥 Transkriptor — Vozes separadas: transcricao_HHhMM_diarizado.txt".
- Notificação toast em erro: "⚠️ Transkriptor — Erro: <mensagem>. Veja o log."
- Usar `win10toast` (pip install win10toast) ou `plyer` (mais multiplataforma).
- As notificações respeitam "Não perturbe" do Windows (win10toast já faz isso).

### 3.3 Pasta de transcrições como UX (UX-03)

**Problema:** Nomes técnicos, sem preview.
**Correção:**
- No assistente web, a rota `/api/transcricoes` retorna metadados em vez de só nomes:
  ```json
  [{"arquivo": "transcricao_2026-07-04_18h07.txt",
    "data": "04/07/2026 18:07",
    "tipo": "transcrição",
    "tamanho_kb": 12.5,
    "preview": "Olá pessoal, bom dia a todos..."}]
  ```
- O dropdown do assistente mostra: `"04/07/2026 18:07 — Olá pessoal, bom dia..."` em vez do nome técnico.
- Arquivos `_diarizado.txt` são agrupados visualmente com sua transcrição original (ou marcados com badge "com vozes").
- No menu da bandeja, "Abrir pasta de transcrições" abre o Explorer com a visão de detalhes.

### 3.4 Sem contexto de conversa no assistente (UX-04)

**Problema:** Cada pergunta é isolada; follow-ups não funcionam.
**Correção:**
- No frontend JS, manter array `historico = []`.
- A cada pergunta, adicionar `{"role":"user","content":pergunta}` e, quando a resposta chegar, adicionar `{"role":"assistant","content":resposta}`.
- Enviar o histórico completo a cada requisição (além do system prompt com a transcrição).
- Limite do histórico: últimas 20 mensagens (para não estourar o contexto do modelo).
- Botão "Limpar conversa" no assistente que zera o array.
- O backend `/api/chat` recebe `historico` (array de messages) e o inclui no payload do Ollama entre o system e a pergunta atual.

**Payload revisado:**
```json
{
  "modelo": "granite4.1:3b",
  "transcricao": "transcricao_teste.txt",
  "pergunta": "me detalhe o item 3",
  "historico": [
    {"role": "user", "content": "liste os pontos principais"},
    {"role": "assistant", "content": "1. ... 2. ... 3. ..."}
  ]
}
```

### 3.5 Sem estado de loading no assistente (UX-05)

**Problema:** Respostas longas sem feedback de progresso ou opção de cancelar.
**Correção:**
- Adicionar botão "Parar" (■) visível durante o streaming que aborta o `fetch` via `AbortController`.
- Cronômetro discreto ao lado dos 3 pontos animados: "Processando... 3s" (atualizar a cada segundo).
- Após 15s sem primeiro token, mudar mensagem para "O modelo está pensando... (pode levar alguns segundos)".
- Barra de progresso sutil (indeterminada) no topo do chat durante o processamento.

### 3.6 Acessibilidade (UX-06)

**Problema:** Foco invisível, sem ARIA, contraste insuficiente, sem teclado.
**Correção:**

**Contraste:**
- `--text-3` de `#5e5852` para `#807a73` (ratio 4.6:1 sobre `#0a0a0f` — passa WCAG AA).
- `--text-2` de `#a8a29b` manter (já passa).
- `--border` de `rgba(255,255,255,0.06)` para `rgba(255,255,255,0.10)` para bordas de elementos interativos (ratio 3:1 — passa WCAG AA para componentes).

**Foco visível:**
- Adicionar `:focus-visible` em todos os elementos interativos (action-cards, selects, botão, textarea):
  ```css
  .action-card:focus-visible, select:focus-visible,
  button:focus-visible, textarea:focus-visible {
    outline: 2px solid var(--gold-bright);
    outline-offset: 2px;
  }
  ```

**ARIA e semântica:**
- Action-cards: mudar de `<div>` para `<button>` com `role="button"` e `aria-label` descritivo (ex.: "Resumir reunião com IA").
- Selects: adicionar `<label>` associado via `for`/`id` (atualmente só `.field-label` visual).
- Chat: `role="log"` com `aria-live="polite"` para o conteúdo do chat (leitores de tela anunciam novas mensagens).
- Empty state: `role="status"`.
- Ícone do Ollama: `aria-label="Status: conectado"` ou `aria-label="Status: offline"`.

**Navegação por teclado:**
- Action-cards como `<button>` já ganham Tab e Enter nativamente.
- Adicionar suporte a setas ↑↓ para navegar entre action-cards (via JS `keydown`).
- textarea: foco automático ao carregar a página.
- Modal de alerta (atualmente `alert()`) → substituir por toast inline no chat.

---

## 4. Watchdog de Threads (Nova Funcionalidade)

**Arquivo:** `watchdog.py`

**Problema:** Se `_capturar` ou `_processar` morrerem, o app continua "rodando" mas nada é transcrito.
**Solução:**
- Classe `Watchdog` que roda em thread própria.
- A cada 10s, verifica:
  - `transcritor.rodando == True` mas `thread_cap` não está viva → reiniciar captura.
  - `transcritor.rodando == True` mas `thread_proc` não está viva → reiniciar processamento.
  - Flask do assistente: se `_assistente_rodando == True` mas processo morreu → marcar como parado.
- Ao reiniciar uma thread, notificar via `on_status`: "Thread de captura reiniciada (watchdog)."
- Limite de 3 reinícios consecutivos; se ultrapassar, notificar erro crítico e parar.

**Interface:**
```python
class Watchdog:
    def __init__(self, app_Transkriptor, intervalo=10):
        self.app = app_Transkriptor
        self.intervalo = intervalo
        self._stop = threading.Event()
        self._reinicios = {"captura": 0, "processar": 0}

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while not self._stop.is_set():
            self._verificar()
            self._stop.wait(self.intervalo)

    def _verificar(self):
        # verifica threads do transcritor, reinicia se mortas
        ...
```

---

## 5. Configuração Centralizada (Nova Funcionalidade)

**Arquivo:** `config.py`

Centraliza todos os parâmetros que estão espalhados como magic numbers:

```python
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_TRANSCRICOES = os.path.join(BASE_DIR, "transcricoes")
LOG_FILE = os.path.join(BASE_DIR, "Transkriptor.log")
ICONE_FILE = os.path.join(BASE_DIR, "Transkriptor.ico")

SAMPLE_RATE = 16000
CHUNK_SEGUNDOS = 25.0
MODELO_WHISPER = "base"
IDIOMA = "pt"
COMPUTE_TYPE = "int8"

OLLAMA_URL = "http://localhost:11434"
PORTA_ASSISTENTE = 5050

INTERVALO_MONITOR_MEET = 5        # segundos
CONFIRMACAO_INICIO_MEET = 2       # ciclos consecutivos
CONFIRMACAO_FIM_MEET = 3          # ciclos consecutivos
INTERVALO_WATCHDOG = 10           # segundos
LIMITE_REINICIOS = 3

LIMIAR_COSSENO_DIARIZACAO = 0.25
DURACAO_MIN_SEGMENTO = 0.5
MAX_HISTORICO_CHAT = 20
```

Todos os módulos importam de `config.py` em vez de definir suas próprias constantes.

---

## 6. Dependências

### requirements.txt (revisado)
```
# Torch deve ser instalado separadamente com index CUDA:
#   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
torch>=2.0
torchaudio>=2.0

faster-whisper==1.1.1
soundcard==0.4.3
numpy>=1.24
pystray==0.19.5
pygetwindow==0.0.9
pillow>=10.0
speechbrain>=1.0
scikit-learn>=1.3
flask>=3.0
win10toast>=0.0
```

### instalar.bat (revisado)
```bat
@echo off
chcp 65001 >nul
echo ============================================
echo   Instalando Transkriptor 1.1
echo ============================================
echo [1/3] Instalando PyTorch (CUDA)...
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
echo [2/3] Instalando dependencias...
python -m pip install -r requirements.txt
echo [3/3] Criando atalhos...
powershell -ExecutionPolicy Bypass -File criar_atalhos.ps1
echo Concluido.
pause
```

---

## 7. Critérios de Aceite

### Engenharia
- [ ] `self._rodando` removido; `self.rodando` é o único atributo de estado
- [ ] Reunião de 1h não ultrapassa 50 MB de RAM (medir com `psutil`)
- [ ] 0 falsos-positivos em 30 min de uso normal do navegador
- [ ] Debounce de 2 ciclos para iniciar, 3 para parar
- [ ] `porta_livre()` lança exceção se nenhuma porta livre
- [ ] Erro do navegador/Flask aparece no status da bandeja e no log
- [ ] Diarização roda em thread separada; monitor de Meet continua ativo durante
- [ ] Arquivo `.txt` sempre fechado mesmo com exceção em `_processar`
- [ ] Segmentos sobrepostos normalizados antes da extração de embeddings
- [ ] Atalho em `shell:startup` funciona após reiniciar
- [ ] `transcrever_meet.py` tem <50 linhas e usa `Transcritor`
- [ ] `pip install -r requirements.txt` + torch traz todas as dependências

### UX
- [ ] Ícone da bandeja muda de cor conforme estado
- [ ] Toast aparece ao iniciar/parar/concluir diarização/erro
- [ ] Dropdown do assistente mostra data + preview em vez de nome técnico
- [ ] Follow-up "me detalhe o item 3" funciona (histórico enviado)
- [ ] Botão "Parar" cancela o streaming
- [ ] Cronômetro de tempo decorrido visível durante processamento
- [ ] Contraste AA validado em todos os textos
- [ ] Tab navega por todos os elementos interativos
- [ ] Leitor de tela anuncia novas mensagens no chat (`aria-live`)

### Robustez
- [ ] App sobrevive 24h de execução contínua sem travar
- [ ] Watchdog reinicia thread morta dentro de 10s
- [ ] 3 reinícios consecutivos = notificação de erro crítico
