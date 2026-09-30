# Protocolo de execução para LLM — SDD v2.0

Normativo para qualquer LLM que implemente a v2.0. A ordem de precedência é a da v1.8 (`v1.8/executor-llm.md` §0), com os documentos da v2.0 no lugar dos da v1.8 quando o assunto for nomes, relógio, provedores de IA ou instalação. Em caso de conflito, registre e pare.

## 1. Escopo

Uma autorização para "executar a v2.0" cobre apenas a task corrente:

- código, testes e documentação da task;
- testes locais;
- o commit local previsto.

Ela **não** cobre, sem autorização separada:

- push, PR, publicação na Chrome Web Store/Edge Add-ons, tag, release ou bump de `config.VERSAO`;
- instalar a extensão no perfil pessoal, registrar o host nativo no HKCU real ou rodar o setup fora de VM/Sandbox;
- usar chave OpenRouter real, abrir `config_user.json`, transcrições, áudios ou embeddings reais;
- entrar em reunião real, reproduzir ou capturar áudio (gate) sem avisar;
- instalar Ollama, baixar modelos grandes ou rodar `winget` na máquina do usuário.

## 2. Leitura obrigatória por sessão

```powershell
git status --short --branch
git rev-parse HEAD
python -c "import config; print(config.VERSAO)"
Get-Content AGENTS.md
Get-Content docs/sdd/v2.0/README.md, docs/sdd/v2.0/diagnostico.md, docs/sdd/v2.0/concept.md
Get-Content docs/sdd/v2.0/spec.md, docs/sdd/v2.0/plan.md, docs/sdd/v2.0/tasks.md
Get-Content docs/sdd/v2.0/decisoes-usuario.md, docs/sdd/v2.0/interfaces.md
python scripts/verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v2.0
```

## 3. Regras específicas

- **Protocolo do Meet:**
  - Escreva decodificadores próprios, tolerantes a campos desconhecidos, com testes sobre fixtures sintéticas.
  - Não inclua bytes capturados de reuniões reais no repositório.
  - Não copie código, nomes de mensagens ou esquemas da Tactiq.
- **Escrita no protocolo:** só o pedido de idioma (B1) e o ack de legenda (já existente). Um teste deve provar que nenhum outro `send` é feito pela extensão.
- **Relógio:** todo horário novo é época em ms com a base declarada. Não misture `Date.now()` do service worker com `performance.now()` da página sem o delta medido.
- **Privacidade:**
  - texto, nome e chat não entram em log, `/api/estado`, telemetria, esqueleto nem evidência;
  - as evidências usam fixtures;
  - a chave do OpenRouter só existe em memória durante a chamada e cifrada por DPAPI no disco.
- **Rede:** só o processo Python fala com `openrouter.ai`; o front continua `connect-src 'self'`. Os testes nunca acessam a rede (HTTP simulado).
- **Captura:** mexeu em `audio_fontes.py`/`transcricao_core.py`? Rode `tests/test_diagnostico.py`, `tests/test_com_audio.py`, `tests/test_lock_sem_callback.py` e o gate de 25 s.
- **Arquivos Python ≤ 500 linhas;** divida o módulo quando o limite se aproximar.

## 4. Algoritmo por task

1. Confirmar dependências e DPs respondidas. Se faltar alguma, marcar a task `BLOCKED` e parar.
2. Rodar o verificador com `--tarefa`.
3. Escrever o RED, rodar e registrar a falha esperada.
4. Implementar e chegar ao GREEN.
5. Rodar o teste final da task e a regressão da fase.
6. Escrever `evidencias/T-15.Xn.md`: requisito, arquivos, comandos, contagens, SHA, limites e o que não foi verificado.
7. Marcar `DONE` na task com commit e evidência.
8. Fazer um commit.

## 5. Paradas obrigatórias

Pare e consulte o usuário se:

- um teste só passa enfraquecendo uma asserção de privacidade;
- a fixture exigir bytes reais;
- o Meet de teste mostrar comportamento visível a outros participantes;
- o custo de `word_timestamps` passar de 15%;
- a loja pedir permissão nova;
- ocorrer qualquer divergência com `interfaces.md`.
