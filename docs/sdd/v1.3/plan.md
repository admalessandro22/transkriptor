# Plan — Transkriptor v1.3

Ordem de execução, dependências e gates. **Uma fase só começa com a anterior verde.**

```text
F1 higiene + git + versão única
  └─► F2 gravação local garantida        ← requisito central do usuário
        └─► F3 atalho global Ctrl+Espaço
              └─► F4 assistente Ollama confiável
                    └─► F5 nomes das vozes robustos
                          └─► F6 robustez + Whisper auto por hardware
                                └─► F7 instalador
                                      └─► F8 refatoração final
```

Racional: F1 habilita commits/rollback (pré-requisito do método); F2 é o requisito central
("nenhuma reunião se perde") e vem antes de tudo que toca o pipeline; F3/F4 são as dores
de uso diário (ativação e Ollama); F5/F6 melhoram a qualidade do resultado; F7 depende de
F1 (versão) e F6 (modelo auto) para instalar certo; F8 é refatoração pura e vai por último
para não misturar com features.

## Método por tarefa

1. `superpowers:test-driven-development` — escrever teste RED citando o ID da spec.
2. Implementação mínima até GREEN.
3. Gate da fase + `superpowers:verification-before-completion`.
4. Commit em português, imperativo, um por tarefa.
5. Se o gate falhar: `superpowers:systematic-debugging`; **não** avançar de fase.

## Gates de verificação

| Fase | Gate |
|------|------|
| F1 | `git log --oneline` mostra commits; `python -m pytest tests/ -q` 100% verde; `python -m pytest tests/test_versao.py -v` |
| F2 | `python -m pytest tests/test_retencao_audio.py tests/test_gravacao_garantida.py tests/test_retranscritor.py tests/test_transkiptor_estado.py -v` + manual: matar o Whisper (renomear cache do modelo), rodar reunião, confirmar áudio salvo e retranscrição pelo menu |
| F3 | `python -m pytest tests/test_hotkey_global.py tests/test_atalho_desktop.py -v` + manual: Ctrl+Espaço inicia/para transcrição com o app na bandeja |
| F4 | `python -m pytest tests/test_assistente_api.py tests/test_assistente_ollama.py tests/test_assistente_seguranca.py tests/test_token_sessao.py -v` (fake Ollama, sem rede) |
| F5 | `python -m pytest tests/test_correlacionador.py tests/test_meet_bridge.py tests/test_meet_bridge_seguranca.py tests/test_extensao_parsing.py tests/test_diarizacao_voce.py tests/test_audio_utils.py -v` |
| F6 | `python -m pytest tests/test_watchdog.py tests/test_transcricao_stop.py tests/test_config_user_modulo.py tests/test_modelo_whisper_auto.py -v` |
| F7 | `python -m pytest tests/test_instalador_helper.py tests/test_atalho_desktop.py -v` + execução manual de `instalar.bat` em prompt limpo |
| F8 | `python -m pytest tests/ -q` 100% verde + verificação de limite de 500 linhas por arquivo de produção |

**Gate final (release):** suíte completa verde + roteiro manual registrado em
`docs/VERIFICACAO.md`: reunião real de 10 min com 2+ participantes e legendas ativas →
(1) transcrição diarizada com nomes salva; (2) áudio em `transcricoes/audio/*.enc`;
(3) Ctrl+Espaço alterna transcrição manual; (4) pergunta ao assistente sobre o fim da
reunião respondida corretamente; (5) simular falha de modelo e recuperar via
"Retranscrever áudio…".

## Rollback

- Cada fase é uma sequência de commits pequenos; rollback = `git revert` dos commits da fase.
- F2: se a conversão `.wav.enc` falhar em produção, o WAV plaintext permanece (perda de
  confidencialidade temporária, nunca perda de dados) e é convertido no próximo start.
- F4 mantém compatibilidade: se `/api/show` falhar, cai no corte fixo atual com aviso.
- F6: `modelo_whisper: "auto"` com falha de CUDA cai para `small`/CPU em runtime (try/except
  no carregamento com re-tentativa CPU).
- F7 mantém `instalar_legacy.bat` até o gate manual passar.

## Riscos por fase

| Fase | Risco | Motivo / mitigação |
|------|-------|--------------------|
| F1 | Baixo | Sem código de produção |
| F2 | Médio | Toca o ciclo de vida do WAV; mitigado por testes de falha injetada e recuperação no start |
| F3 | Médio | Win32 message loop; testável com mock + 1 verificação manual |
| F4 | Médio | Map-reduce muda UX de reuniões longas |
| F5 | Alto | DOM do Meet é alvo móvel; fixtures + fallback em camadas |
| F6 | Médio | `medium`/CUDA na GTX 1650 divide VRAM com Ollama — mitigado porque o assistente é usado após a reunião; fallback CPU automático |
| F7 | Baixo | Lógica isolada em helper testável |
| F8 | Médio | Refatoração ampla; suíte 100% verde antes e depois |
