# Manual do Usuário — Transkriptor v1.5

Transkriptor é um aplicativo para **Windows** que fica na **bandeja do sistema**, detecta **Google Meet**, transcreve o áudio em segundo plano (Whisper offline), separa vozes (diarização) e oferece um **assistente local** via Ollama.

Durante uma reunião aceita, o aplicativo faz apenas a captura leve do áudio. O
Whisper e a separação de vozes entram no **processamento após a reunião**, em um
processo separado e de prioridade baixa. Isso mantém a chamada responsiva.

Tudo roda no seu computador — transcrições e perfis de voz ficam em disco local.

---

## 1. Instalação

### Requisitos

- Windows 10 ou 11
- Python 3.12 ou superior
- Microfone (para identificar sua voz como `VOCÊ`)
- Opcional: GPU NVIDIA com CUDA (acelera o Whisper)
- Opcional: [Ollama](https://ollama.com) instalado (assistente de resumo/perguntas)
- Opcional: Google Chrome (extensão para nomes no Meet)

### Passo a passo

1. Extraia ou clone o projeto em uma pasta, por exemplo `C:\projetos\trancricaoreunioes`.
2. Instale o PyTorch conforme sua GPU (veja `requirements.txt`).
3. Execute `instalar.bat` — cria `.venv`, instala PyTorch (GPU se houver), dependências,
   atalho na Área de Trabalho e (opcional) faz warm-up dos modelos.
4. Inicie pelo atalho **Transkriptor** ou `iniciar_bandeja.bat` (usa o `.venv`).
5. O ícone aparece na bandeja (seta ^ se estiver oculto).
6. Para remover: `desinstalar.bat` (preserva `transcricoes/` e config por padrão).

### Primeira execução

- O app cria a pasta `transcricoes/`; toda reunião concluída gera um `.txt` legível.
- Na primeira execução, gera a chave local protegida por DPAPI em
  `_modelo_voz/transkriptor_key.dpapi`, separada da configuração.
- Modelos Whisper e de voz baixam no primeiro processamento após uma reunião
  (pode demorar alguns minutos).
- Apenas **uma instância** pode rodar; uma segunda exibe aviso e encerra.

---

## 2. Bandeja do sistema

Clique com o **botão direito** no ícone da bandeja para abrir o menu.

| Item | Função |
|------|--------|
| Status | Mostra detecção, gravação e `Em fila`, `Processando`, `Pronta` ou `Falhou` |
| Abrir pasta de transcrições | Abre `transcricoes/` no Explorer |
| Diagnóstico (por que não está gravando?) | Testa áudio e detecção e abre um relatório |
| Abrir log | Abre `transkriptor.log` para diagnóstico |
| Retranscrever áudio… | Reprocessa um áudio salvo em `transcricoes/audio/` |
| Abrir assistente | Abre o assistente web local (Ollama) |
| Pausar gravação automática | Exige confirmação; enquanto pausado **não grava** reuniões |
| Confirmar antes de gravar | Regra obrigatória: somente **Sim** permite capturar |
| Ativar/desativar separação de vozes | Liga ou desliga diarização ao final |
| Cadastrar minha voz (20s) | Grava perfil de voz pelo microfone |
| Identificar minha voz | Toggle do rótulo `VOCÊ` na diarização |
| Apagar perfil de voz | Remove perfil de voz (`perfil_usuario.enc` ou legado `.npz`) |
| Identificar nomes do Meet | Ativa ponte WebSocket para extensão Chrome |
| Modo legendas Meet (Tactiq) | Prioriza legendas CC do Meet |
| Instalar extensão Meet (pasta) | Abre pasta `extension/meet/` |
| Renomear falante (última diarização) | Salva nome+embedding para reuniões futuras |
| Abrir pasta vozes conhecidas | Pasta `_modelo_voz/` (`vozes_conhecidas.enc` ou legado `.json`) |
| Criar cópia criptografada (.tkpt) | Mantém uma cópia protegida além do `.txt` principal |
| Iniciar com o Windows | Atalho na pasta Startup |
| Sair | Encerra o app (confirma se estiver gravando) |

### Cores do ícone

- **Verde** — gravando a reunião, sem carregar a IA
- **Roxo** — processando a reunião depois do encerramento
- **Azul** — aguardando reunião
- **Cinza** — detecção pausada
- **Vermelho** — erro crítico (reverte após ~30 s)

### Notificações

- Durante a reunião não aparecem trechos, balões, janelas ou sons por bloco.
- O estado fica no ícone, tooltip e primeira linha do menu.
- Ao terminar ou falhar o processamento, pode aparecer uma única notificação
  usando o mesmo ícone da bandeja.

### Como abrir e fechar

O Transkriptor **não usa atalho de teclado**. Para abrir, dê **dois cliques** no atalho
"Transkriptor" da Área de Trabalho (ou em `iniciar_bandeja.bat` / `transkriptor.pyw`).
O app fica **na bandeja do sistema até ser fechado** pelo menu (**Sair**). Abrir de novo
com ele já rodando apenas avisa que já está em execução — nunca cria segunda instância.

Não existe comando de gravação genérica ou transcrição manual. O atalho `.lnk`
da Área de Trabalho apenas inicia o detector e não tem tecla de atalho associada.

---

## 3. Transcrição automática (Google Meet)

1. Deixe o Transkriptor na bandeja com detecção **ativa**.
2. Entre em uma reunião no Google Meet (Chrome, Edge, etc.) ou no Zoom.
3. Em cerca de 10 segundos, um diálogo pergunta se você quer gravar **antes de abrir**
   o dispositivo ou criar qualquer arquivo.
4. Somente **Sim** inicia a captura. **Não**, falta de resposta em 30 segundos ou
   erro no diálogo não gravam nada e não repetem a pergunta na mesma reunião.
5. Durante a chamada, o app apenas grava o áudio em disco, sem Whisper, diarização,
   trechos na tela ou notificações por bloco.
6. Quando título e extensão deixam de confirmar a reunião por cerca de 30 segundos,
   a captura fecha os WAVs e entra na fila de processamento.
7. O menu passa por `Em fila` → `Processando` → `Pronta` (ou `Falhou`). O `.txt`
   aparece na raiz de `transcricoes/` quando estiver pronto.

### Como o Transkriptor sabe que há uma reunião

Ele observa três fontes, mas apenas sinais fortes podem iniciar a gravação ou
mantê-la indefinidamente:

| Sinal | O que observa | Cobre |
|-------|---------------|-------|
| **Título da janela** | `Meet – abc-defg-hij`, `<sala> - Google Meet`, `Zoom Meeting` | O caso comum |
| **Microfone em uso** | Indicador auxiliar do Windows | Diagnóstico; nunca inicia nem mantém a gravação sozinho |
| **Extensão do Meet** | A própria página da reunião (opcional — seção 6) | Certeza total |

Por que combinar: o título só mostra a **aba que está na frente**. A extensão do
Meet mantém a reunião confirmada quando você troca de aba. Sem título nem extensão,
a janela de graça termina mesmo que algum programa continue usando o microfone.

Áudio do WhatsApp, música, vídeo, ditado e microfone isolado não iniciam reunião.
Depois do encerramento detectado, nada do restante do computador é capturado.

### Arquivos gerados

Para cada reunião processada:

- `transcricao_AAAA-MM-DD_HhMM.txt` — **arquivo principal**, UTF-8, com início,
  fim, duração, timestamps e texto.
- `transcricao_*_diarizado.txt` — versão adicional com rótulos de falante, se ativa.
- `transcricao_*.tkpt` — cópia criptografada adicional, quando habilitada; nunca
  substitui nem apaga o `.txt` principal.
- `audio/transcricao_*_audio.wav` (ou `.wav.enc`) — loopback preservado até a retenção.
- `audio/transcricao_*_mic.wav` (ou `.wav.enc`) — microfone paralelo, se ativo.
- `.jobs_processamento/*.json` — estado técnico da fila, sem conteúdo falado.

O áudio é mantido quando o processamento falha, para permitir nova tentativa.
Quando o resultado existe, a retenção remove áudios antigos conforme a configuração.

### Por que não grava outros áudios

Não há botão que ignore o detector. A captura só nasce depois de uma fonte forte
de Meet/Zoom e do seu **Sim**. Ao perder a fonte forte, ela termina mesmo se o
WhatsApp, navegador, player ou microfone continuarem produzindo áudio.

---

## 4. Diarização (separação de vozes)

Com **separação de vozes** ativa, o worker de processamento após a reunião:

1. Analisa trechos de áudio com modelo ECAPA (SpeechBrain)
2. Agrupa vozes semelhantes em `FALANTE_00`, `FALANTE_01`, …
3. Gera `*_diarizado.txt` com formato:

```
[Ana Silva 00:01-00:05] Bom dia a todos.
[VOCÊ 00:05-00:08] Obrigado por participar.
```

A diarização roda no subprocesso de prioridade baixa. A bandeja continua
responsiva e consegue detectar e capturar uma nova reunião.

---

## 5. Identificação da sua voz (`VOCÊ`)

O áudio do Meet pelo alto-falante **não inclui sua voz** na maioria dos casos. O Transkriptor usa:

1. **Perfil cadastrado** — 20 s de fala no seu microfone
2. **Gravação paralela do mic** durante a reunião
3. **Matching** por similaridade de embedding na diarização

### Cadastrar perfil

1. Menu → **Cadastrar minha voz (20s)**
2. Após o aviso, fale em voz alta por 20 segundos (leia um texto)
3. Toast confirma **Perfil de voz salvo**

### Usar na reunião

- Mantenha **Identificar minha voz** marcado (✓)
- Use fone ou microfone aberto no Meet
- Se o mic estiver mudo, o reforço `VOCÊ` pode falhar

### Apagar perfil

Menu → **Apagar perfil de voz**

---

## 6. Nomes no Meet (extensão Chrome)

Para substituir `FALANTE_XX` por **nomes reais** dos participantes.

**Guia completo de instalação:** [`extension/meet/README.md`](../extension/meet/README.md) (passo a passo, solução de problemas e privacidade).

### Configuração

1. Menu → **Identificar nomes do Meet** (ativa ponte em `127.0.0.1:5051`)
2. Menu → **Instalar extensão Meet (pasta)** — ou siga o [README da extensão](../extension/meet/README.md)
3. No Chrome: `chrome://extensions` → Modo desenvolvedor → **Carregar sem compactação** → selecione `extension/meet/`
4. Entre no Meet com a extensão habilitada

A extensão **não aparece** na reunião como participante nem bot — funciona em silêncio no navegador.

### Modo legendas (recomendado)

1. Ative **legendas (CC)** no Google Meet
2. Menu → **Modo legendas Meet (Tactiq)**
3. A extensão lê o nome do falante nas legendas

Se o modo legendas estiver ativo mas nenhum evento for recebido, você verá o aviso: *"Ative legendas no Meet para identificar participantes"*.

### Prioridade de rótulos

```
Nome do Meet  >  Nome cadastrado (vozes conhecidas)  >  VOCÊ  >  FALANTE_XX
```

### Renomear falante manualmente

Após uma diarização:

1. Menu → **Renomear falante (última diarização)**
2. Informe o rótulo (`FALANTE_01`) e o nome desejado (ex.: Carlos)
3. O embedding é salvo em `vozes_conhecidas.enc` (ou `.json` legado) para próximas reuniões

---

## 7. Assistente Ollama (resumo e perguntas)

### Pré-requisito

Instale e inicie o **Ollama** com pelo menos um modelo (ex.: `ollama pull llama3.2`).

### Abrir

Menu → **Abrir assistente (resumo, perguntas)**

O navegador abre `http://127.0.0.1:PORTA/?token=...` — porta automática (5050, 5052, …; **5051** reservada para Meet).

### Uso

1. Selecione uma transcrição no dropdown
2. Transcrições diarizadas com suas falas aparecem marcadas como **com sua voz** no dropdown e nos metadados (tamanho do arquivo)
3. Use cartões de ação: resumo, pontos principais, tarefas, decisões
4. Ou digite perguntas livres no chat
5. Botão **Copiar resposta** guarda a última resposta da IA

O assistente lê `.tkpt` e `.txt` automaticamente. O `.txt` principal também abre
diretamente no Bloco de Notas ou editor de sua preferência.

### Sem Ollama

A transcrição continua funcionando; apenas o assistente fica indisponível.

---

## 8. Segurança e privacidade (uso local)

| Tópico | Comportamento |
|--------|----------------|
| Rede | Assistente e ponte Meet escutam só em `127.0.0.1` (localhost) |
| API | Rotas `/api/*` exigem token (`X-Transkriptor-Token` ou `?token=`) |
| Arquivos | API rejeita paths com `../` (403) |
| XSS | Nomes de arquivo não são injetados via `innerHTML` no assistente |
| Logs | Conteúdo de transcrições **não** é gravado no log |
| Dados sensíveis | `transcricoes/`, perfil de voz e vozes conhecidas ficam locais |
| Criptografia em repouso | Cópia `.tkpt`, áudios `.enc`, perfil e vozes com AES-256-GCM; chave protegida por DPAPI |
| Instância única | Mutex impede duas cópias simultâneas |

### Cópia criptografada (padrão ligado)

- O `.txt` principal permanece legível e deve ser tratado como dado sensível.
- Arquivos `.tkpt` e `.enc` são **ilegíveis** no Bloco de Notas ou Explorer.
- Leitura só pelo Transkriptor e pelo assistente autenticado (token na URL).
- Ativar a cópia criptografada não remove nem substitui arquivos `.txt`.
- Se a chave DPAPI não puder ser aberta (outro usuário Windows, perfil corrompido), a criptografia fica indisponível até o problema ser resolvido — arquivos antigos **não** são apagados.

### Boas práticas

- Restrinja o acesso à pasta `transcricoes/`, pois o resultado principal é `.txt`.
- Não copie `transkriptor_key.dpapi` entre usuários Windows diferentes (a chave é por usuário).
- Feche o assistente quando não estiver em uso (aba do navegador).
- Mantenha o Windows e o Chrome atualizados.

---

## 9. Configurações (`config_user.json`)

Arquivo na raiz do projeto (criado/atualizado pelo menu):

```json
{
  "versao_config": 2,
  "iniciar_com_windows": false,
  "criptografar_transcricoes": true,
  "backup_txt_na_migracao": false,
  "identificar_minha_voz": true,
  "rotulo_usuario": "VOCÊ",
  "capturar_mic": true,
  "usar_nomes_meet": false,
  "modo_legendas_meet": false,
  "meet_bridge_token": "<gerado automaticamente>"
}
```

Constantes globais ficam em `config.py` (modelo Whisper, portas, limiares). A
confirmação antes de gravar é obrigatória e não aparece como configuração. A
chave DPAPI fica no arquivo dedicado `_modelo_voz/transkriptor_key.dpapi`.

---

## 10. Solução de problemas

### Ícone não aparece na bandeja

- Clique na seta **^** na barra de tarefas
- Verifique se não há segunda instância bloqueada no log

### Nada é gravado — comece pelo Diagnóstico

Menu da bandeja → **Diagnóstico (por que não está gravando?)**. Ele grava meio
segundo de áudio de verdade, consulta as três fontes de detecção e abre um
relatório dizendo, item a item, o que está `OK`, `AVISO` ou `ERRO`.

Leia primeiro as linhas com **ERRO** — são as que impedem a gravação. `AVISO`
costuma ser normal (por exemplo, "loopback em silêncio" quando nada está tocando).

### Meet não inicia transcrição

- Confirme que a detecção não está pausada (o status do menu diz o que ele vê agora)
- Confirme que respondeu **Sim** ao diálogo; qualquer outra resposta não grava
- Rode o **Diagnóstico** e veja a linha `Fonte: titulo` — ela mostra se alguma
  janela foi reconhecida
- Com `exigir_janela_visivel` ativo, janela minimizada não conta

### WhatsApp, vídeo ou música iniciou gravação

Na v1.5 isso não deve acontecer: microfone e áudio do sistema não iniciam reunião.
Abra o menu e confirme o status. Se estiver `Gravando reunião`, use **Diagnóstico**
para identificar qual título ou extensão está sendo tratado como fonte forte e
anexe o relatório ao suporte; ele não inclui o conteúdo falado.

### Gravou, mas a transcrição saiu vazia

Sinal clássico de captura de áudio quebrada: o arquivo em `transcricoes/audio/`
fica com pouquíssimos bytes.

- Rode o **Diagnóstico**: a linha `soundcard` aponta incompatibilidade de versão
- Correção: `pip install -U "soundcard>=0.4.6"` (versões anteriores não funcionam
  com numpy 2)
- Confira também se o dispositivo de saída do Windows não mudou (fone conectado
  no meio da reunião)

### "Já está em execução" mas não há ícone na bandeja

A partir da v1.5 isso não deve mais acontecer: o controle de instância única usa
um mutex do Windows, liberado pelo sistema mesmo se o app for encerrado à força.
Se acontecer, feche `pythonw.exe` no Gerenciador de Tarefas e apague
`transkriptor.lock`.

### Diarização não gera arquivo

- Verifique se **separação de vozes** está ativa
- Reunião muito curta pode ter poucos segmentos (1 falante apenas)
- Veja erros em `transkriptor.log`

### O áudio existe, mas o texto ainda não apareceu

- Veja a primeira linha do menu: `Em fila` e `Processando` ainda não são erro
- `Pronta` indica um `.txt` na raiz de `transcricoes/`
- `Falhou` preserva o áudio em `transcricoes/audio/`; use **Retranscrever áudio…**
- O primeiro processamento pode demorar mais por causa do download dos modelos

### `VOCÊ` não aparece

- Cadastre o perfil de voz (20 s)
- Ative **Identificar minha voz**
- Verifique se o microfone captura durante a reunião
- Headset com cancelamento agressivo pode atrapalhar

### Nomes do Meet não aparecem

- Extensão instalada e Meet aberto no Chrome?
- **Identificar nomes do Meet** ativo na bandeja?
- Legendas CC ativas (modo Tactiq)?
- Firewall bloqueando `127.0.0.1:5051`?

### Assistente não abre

- Ollama rodando? (`ollama serve`)
- Porta ocupada — veja log; app tenta portas alternativas
- Aguarde até 10 s no primeiro acesso

### Transcrições ilegíveis ou erro ao abrir arquivo

- Abra o `.txt` principal; `.tkpt` é apenas a cópia criptografada adicional
- Chave DPAPI inválida: verifique se está no mesmo usuário Windows que criou os arquivos
- Reinicie o app após trocar de conta Windows

### Erro crítico (ícone vermelho)

- Abra **Abrir log** no menu
- Reinicie o Transkriptor
- Verifique espaço em disco e permissões da pasta

---

## 11. Estrutura de pastas

```
Transkriptor/
├── transkriptor.pyw         # App principal (bandeja)
├── app_processamento.py     # Fila e worker depois da reunião
├── crypto_storage.py        # Criptografia .tkpt / .enc
├── transcricao_core.py      # Captura leve; IA opcional fora da reunião
├── fila_processamento.py    # Jobs atômicos pending/processing/ready/failed
├── processador_reuniao.py   # Subprocesso Whisper/diarização
├── retranscritor.py         # Geração do .txt principal
├── assistente.py            # Interface web + Ollama
├── diarizador.py            # Separação de vozes
├── identificador_voz.py     # Perfil VOCÊ + vozes conhecidas
├── meet_bridge.py           # WebSocket Meet
├── correlacionador.py       # Nomes ↔ segmentos
├── extension/meet/          # Extensão Chrome (+ README de instalação)
├── transcricoes/            # Resultados .txt e cópias .tkpt opcionais
├── _modelo_voz/             # Perfil (.enc) e vozes conhecidas
└── docs/                    # Documentação
```

---

## 12. Suporte e verificação técnica

Desenvolvedores podem validar a instalação:

```bash
python scripts/verificar_fase.py --fase all
python scripts/verificar_fase.py --fase v1.5-estatico
python -m pytest tests/ -v --tb=short
```

O gate Windows de recursos recebe o PID do processo da bandeja e mede 10 minutos,
sem ler títulos, áudio ou transcrições:

```bash
python scripts/verificar_recursos_gravacao.py --pid 12345 --duracao 600
```

Ele exige crescimento menor que 100 MB, CPU média menor que 10% de um núcleo e
um único ícone pystray. Documentação SDD atual em `docs/sdd/v1.5/`.

---

## 13. Glossário rápido

| Termo | Significado |
|-------|-------------|
| Loopback | Captura do áudio que sai no alto-falante do PC |
| Diarização | Separação automática de quem falou o quê |
| Whisper | Motor de transcrição offline usado pelo Transkriptor |
| Ollama | Servidor local para modelos de linguagem (assistente) |
| ECAPA | Modelo de embedding de voz usado na identificação |
| CC / Legendas | Closed Captions do Google Meet |
| `.txt` | Resultado principal legível, em UTF-8 |
| `.tkpt` | Cópia criptografada adicional (AES-GCM) |
| `.enc` | Perfil de voz e vozes conhecidas criptografados |
| DPAPI | Proteção da chave mestra pelo Windows (por usuário) |

---

*Transkriptor v1.5 — Manual do usuário — 2026*
