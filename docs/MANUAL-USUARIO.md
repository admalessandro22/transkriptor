# Manual do Usuário — Transkriptor v1.3

Transkriptor é um aplicativo para **Windows** que fica na **bandeja do sistema**, detecta **Google Meet**, transcreve o áudio em segundo plano (Whisper offline), separa vozes (diarização) e oferece um **assistente local** via Ollama.

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
3. Execute `instalar.bat` — instala dependências e cria atalhos no desktop.
4. Inicie pelo atalho **Iniciar Transkriptor** ou `iniciar_bandeja.bat`.
5. O ícone aparece na bandeja (seta ^ se estiver oculto).

### Primeira execução

- O app cria a pasta `transcricoes/` e, por padrão, salva transcrições criptografadas em `.tkpt`.
- Na primeira execução, gera a chave local (DPAPI) em `config_user.json`.
- Modelos Whisper e de voz baixam na primeira transcrição (pode demorar alguns minutos).
- Apenas **uma instância** pode rodar; uma segunda exibe aviso e encerra.

---

## 2. Bandeja do sistema

Clique com o **botão direito** no ícone da bandeja para abrir o menu.

| Item | Função |
|------|--------|
| Status | Mostra se está aguardando Meet, transcrevendo ou diarizando |
| Abrir pasta de transcrições | Abre `transcricoes/` no Explorer |
| Abrir log | Abre `transkriptor.log` para diagnóstico |
| Transcrição manual (Ctrl+Espaço) | Inicia/para gravação sem detectar Meet |
| Retranscrever áudio… | Reprocessa um áudio salvo em `transcricoes/audio/` |
| Abrir assistente | Abre o assistente web local (Ollama) |
| Pausar gravação automática | Exige confirmação; enquanto pausado **não grava** reuniões |
| Ativar/desativar separação de vozes | Liga ou desliga diarização ao final |
| Cadastrar minha voz (20s) | Grava perfil de voz pelo microfone |
| Identificar minha voz | Toggle do rótulo `VOCÊ` na diarização |
| Apagar perfil de voz | Remove perfil de voz (`perfil_usuario.enc` ou legado `.npz`) |
| Identificar nomes do Meet | Ativa ponte WebSocket para extensão Chrome |
| Modo legendas Meet (Tactiq) | Prioriza legendas CC do Meet |
| Instalar extensão Meet (pasta) | Abre pasta `extension/meet/` |
| Renomear falante (última diarização) | Salva nome+embedding para reuniões futuras |
| Abrir pasta vozes conhecidas | Pasta `_modelo_voz/` (`vozes_conhecidas.enc` ou legado `.json`) |
| Criptografar transcrições | Toggle (padrão **ligado**): grava `.tkpt` e migra `.txt` legados |
| Iniciar com o Windows | Atalho na pasta Startup |
| Sair | Encerra o app (confirma se estiver gravando) |

### Cores do ícone

- **Verde** — transcrevendo
- **Azul** — aguardando Meet
- **Cinza** — detecção pausada
- **Vermelho** — erro crítico (reverte após ~30 s)

### Notificações (toast)

- Ao transcrever com Meet em segundo plano, trechos aparecem em notificação (60 caracteres).
- Ao terminar a diarização, você recebe aviso com o nome do arquivo.
- Se a gravação estiver pausada e um Meet abrir, um aviso lembra que **não está gravando**.

### Atalho global Ctrl+Espaço

Com o Transkriptor **aberto na bandeja**, use **Ctrl+Espaço** em qualquer aplicativo para
iniciar ou parar a **transcrição manual** (toasts de início/fim). O atalho do arquivo `.lnk`
da Área de Trabalho **não** usa mais Ctrl+Alt — a ativação é só pelo app.

Se o combo estiver em uso por outro programa, o Transkriptor avisa e segue sem o atalho
(o menu da bandeja continua funcionando). O combo pode ser alterado em `config_user.json`
(`atalho_global`, ex.: `"ctrl+shift+t"`).

---

## 3. Transcrição automática (Google Meet)

1. Deixe o Transkriptor na bandeja com detecção **ativa**.
2. Entre em uma reunião no Google Meet (Chrome, Edge, etc.).
3. Quando o título da janela confirmar o Meet, a transcrição **inicia sozinha**.
4. Ao encerrar a reunião (janela fechada ou título sem Meet por alguns ciclos), a gravação **para e salva**.

### Arquivos gerados

Para cada sessão, em `transcricoes/`:

- `transcricao_AAAA-MM-DD_HhMM.tkpt` — texto corrido com timestamps (criptografado por padrão)
- `transcricao_*_diarizado.tkpt` — versão com rótulos de falante (se diarização ativa)
- `transcricao_*_audio.wav` — áudio temporário (removido após diarizar)
- `transcricao_*_mic.wav` — microfone paralelo (se captura ativa)

Com **Criptografar transcrições** desligado, os mesmos arquivos usam extensão `.txt` em texto legível.

### Transcrição manual

Use quando quiser gravar **sem** Meet (entrevista presencial, áudio do PC, etc.):

1. Menu → **Transcrição manual** → inicia
2. Menu → **Transcrição manual** novamente → para e salva

A detecção automática de Meet **não** encerra transcrição manual ao fechar o Meet.

---

## 4. Diarização (separação de vozes)

Com **separação de vozes** ativa, ao final da gravação o app:

1. Analisa trechos de áudio com modelo ECAPA (SpeechBrain)
2. Agrupa vozes semelhantes em `FALANTE_00`, `FALANTE_01`, …
3. Gera `*_diarizado.tkpt` (ou `.txt` se criptografia desligada) com formato:

```
[Ana Silva 00:01-00:05] Bom dia a todos.
[VOCÊ 00:05-00:08] Obrigado por participar.
```

A diarização roda em segundo plano — o monitor de Meet continua funcionando.

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

O assistente lê `.tkpt` e `.txt` automaticamente — arquivos criptografados não abrem no Bloco de Notas, só pelo app.

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
| Criptografia em repouso | Transcrições `.tkpt`, perfil `.enc` e vozes `.enc` com AES-256-GCM; chave protegida por DPAPI (usuário Windows) |
| Instância única | Mutex impede duas cópias simultâneas |

### Criptografia (padrão ligado)

- Arquivos `.tkpt` e `.enc` são **ilegíveis** no Bloco de Notas ou Explorer.
- Leitura só pelo Transkriptor e pelo assistente autenticado (token na URL).
- Na ativação, `.txt` legados em `transcricoes/` migram para `.tkpt` e o plaintext é removido.
- Backup `.txt.bak` na migração só ocorre se `backup_txt_na_migracao: true` em `config_user.json`.
- Se a chave DPAPI não puder ser aberta (outro usuário Windows, perfil corrompido), a criptografia fica indisponível até o problema ser resolvido — arquivos antigos **não** são apagados.

### Boas práticas

- Mantenha **Criptografar transcrições** ligado em máquinas compartilhadas.
- Não copie `config_user.json` entre usuários Windows diferentes (chave DPAPI é por usuário).
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
  "meet_bridge_token": "<gerado automaticamente>",
  "chave_dpapi": "<gerado automaticamente — não editar>"
}
```

Constantes globais em `config.py` (modelo Whisper, portas, limiares).

---

## 10. Solução de problemas

### Ícone não aparece na bandeja

- Clique na seta **^** na barra de tarefas
- Verifique se não há segunda instância bloqueada no log

### Meet não inicia transcrição

- Confirme que a detecção não está pausada
- Título da janela deve conter `- Google Meet` ou `meet.google.com/...`
- Com `exigir_janela_visivel` ativo, janela minimizada não conta

### Diarização não gera arquivo

- Verifique se **separação de vozes** está ativa
- Reunião muito curta pode ter poucos segmentos (1 falante apenas)
- Veja erros em `transkriptor.log`

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

- Com criptografia ligada, `.tkpt` não abre fora do Transkriptor — use o assistente ou desligue o toggle para gravar `.txt` legado
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
├── crypto_storage.py        # Criptografia .tkpt / .enc
├── transcricao_core.py      # Whisper + captura
├── assistente.py            # Interface web + Ollama
├── diarizador.py            # Separação de vozes
├── identificador_voz.py     # Perfil VOCÊ + vozes conhecidas
├── meet_bridge.py           # WebSocket Meet
├── correlacionador.py       # Nomes ↔ segmentos
├── extension/meet/          # Extensão Chrome (+ README de instalação)
├── transcricoes/            # Suas transcrições (.tkpt por padrão)
├── _modelo_voz/             # Perfil (.enc) e vozes conhecidas
└── docs/                    # Documentação
```

---

## 12. Suporte e verificação técnica

Desenvolvedores podem validar a instalação:

```bash
python scripts/verificar_fase.py --fase all
python -m pytest tests/ -v --tb=short
```

Documentação SDD em `docs/sdd/v1.2/`.  
Auditoria: `docs/AUDITORIA-v1.2.md`.

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
| `.tkpt` | Transcrição criptografada (AES-GCM); legível só pelo Transkriptor |
| `.enc` | Perfil de voz e vozes conhecidas criptografados |
| DPAPI | Proteção da chave mestra pelo Windows (por usuário) |

---

*Transkriptor v1.2 — Manual do usuário — 2026*