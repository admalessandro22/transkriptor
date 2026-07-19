# CHANGELOG — Transkriptor v1.2

Registro das fases entregues na auditoria SDD.

## Fase 0 — Fundação QA

- pytest configurado com fixtures compartilhadas
- `scripts/verificar_fase.py` para gates por fase
- Testes baseline do `detector_meet`

## Fase 1 — P0 Crítico

- `caminho_transcricao_seguro` e validação nas rotas API
- Startup thread-first do assistente Flask
- Anti-XSS no select de transcrições (`buildSelectOptions`)

## Fase 2 — Engenharia P1

- Ícone de erro com auto-revert e estado pausado
- `DEVICE_WHISPER = auto`
- Mutex de instância única e log rotation
- `scripts/resolver_pythonw.py` e limpeza de código morto

## Fase 3 — Criptografia em repouso

- `crypto_storage.py`: AES-256-GCM + chave DPAPI
- Transcrições `.tkpt`, migração `.txt` sem plaintext residual
- Perfil e vozes conhecidas em `.enc`

## Fase 4 — UX Bandeja e Assistente

- Toast ao vivo quando Meet não está em foco
- Menu: abrir log, transcrição manual, confirmar saída se gravando
- Progresso de diarização a cada 10 segmentos
- Timer “O modelo está pensando...” após 15s
- Barra de progresso indeterminada durante `busy`
- Drawer mobile (375px) e navegação ↑↓ entre action-cards
- Copiar última resposta e label `tamanho_kb`
- API `/api/transcricoes` com metadados completos

## Fase 5 — Segurança Avançada

- Token de sessão `X-Transkriptor-Token` em rotas `/api/*`
- Flag `exigir_janela_visivel` no detector Meet
- Truncagem de transcrições grandes (`MAX_CHARS_TRANSCRICAO`)

## Fase 6 — Manutenção

- `.gitignore` para artefatos sensíveis e cache
- `docs/VERIFICACAO.md` com gates F0–F7
- Este CHANGELOG

## Fase 7 — Identificação da voz do usuário (`VOCÊ`)

- `identificador_voz.py` — perfil `.npz`, matching por cosseno
- Captura paralela `_mic.wav` em `transcricao_core.py`
- Diarização rotula `VOCÊ` com reforço RMS do microfone
- Menus bandeja: cadastrar (20s), toggle, apagar perfil
- `config_user.json` schema v2

## Fase 8 — Nomes no Meet (opcional)

- `meet_bridge.py` — WebSocket `127.0.0.1:5051` com fila thread-safe
- `correlacionador.py` — janela ±1,5s e prioridade nome Meet > voz conhecida > VOCÊ
- Extensão Chrome MV3 em `extension/meet/`
- Banco `vozes_conhecidas.json` com `renomear_falante`
- Menus bandeja: toggles nomes/legendas Meet, pasta extensão, vozes conhecidas
- Aviso FR-8.8 se modo legendas ativo sem eventos CC