# Plan — Transkriptor v1.4

Ordem de execução, dependências e gates. **Uma fase só começa com a anterior verde.**

```text
F9.A captura de áudio confiável        ← causa raiz 1: nada era gravado
  └─► F9.B detecção multi-fonte        ← causa raiz 2: nada era detectado
        └─► F9.C autodiagnóstico       ← para nenhuma das duas voltar a ser invisível
              └─► F9.D ciclo de vida
                    └─► F9.E qualidade
```

Racional da ordem: F9.A vem primeiro porque, sem captura, consertar a detecção só
faria o app gravar arquivos vazios com mais frequência — o gate de F9.B exige uma
gravação real com quadros. F9.C depende das duas para poder reportá-las. F9.D e
F9.E são endurecimento e não bloqueiam o caminho crítico.

## Método por tarefa

1. Teste RED citando o ID da spec.
2. Implementação mínima até GREEN.
3. Gate da fase.
4. Commit em português, imperativo, um por tarefa.
5. Gate falhou: depurar a causa; **não** avançar de fase.

## Gates de verificação

| Fase | Gate |
|------|------|
| F9.A | `pytest tests/test_diagnostico.py -v` + **manual:** gravar fala real pelos alto-falantes e conferir WAV com quadros (não 77 bytes) e texto na transcrição |
| F9.B | `pytest tests/test_deteccao_multi_fonte.py tests/test_monitor_microfone.py tests/test_detector_meet.py tests/test_integracao_monitor_meet.py -v` + **manual:** janela com título `Meet – abc-defg-hij` reconhecida via `pygetwindow` real |
| F9.C | `pytest tests/test_diagnostico.py -v` + **manual:** menu → Diagnóstico abre relatório com as três fontes listadas |
| F9.D | `pytest tests/test_mutex.py tests/test_aviso_gravacao.py tests/test_bandeja_lifecycle.py -v` |
| F9.E | `pytest tests/test_modelo_whisper_auto.py -v` + `pytest tests/ -q` 100% verde |

**Gate final (release):** reunião real de Google Meet, com o Transkriptor na
bandeja:

1. Entrar na reunião → em até ~10 s o toast "reunião detectada" e o diálogo
   Sim/Não aparecem; o ícone fica verde.
2. Responder **Sim** → trocar de aba por 2 minutos → a gravação **continua**
   (regressão histórica: parava em 15 s).
3. Sair da reunião → em ~30 s a transcrição é finalizada e salva.
4. Conferir `transcricoes/`: `.tkpt` com texto e `transcricoes/audio/*.wav.enc`
   com tamanho compatível com a duração (kilobytes por segundo, não 77 bytes).
5. Menu → Diagnóstico: 0 erros.

## Rollback

- Cada fase é uma sequência de commits pequenos; rollback = `git revert`.
- F9.A: o pin de `soundcard` é a única mudança de ambiente; reverter = reinstalar
  a versão anterior (volta a quebrar a captura em numpy 2 — não recomendado).
- F9.B: `DETECTAR_POR_MICROFONE = False` em `config.py` desliga a fonte fraca sem
  tocar em código, caso apareça falso positivo em campo.
- F9.D: `adquirir_lock` sem `usar_mutex_nomeado` volta ao comportamento v1.3.

## Riscos por fase

| Fase | Risco | Motivo / mitigação |
|------|-------|--------------------|
| F9.A | Baixo | Correção de dependência com teste de gate permanente |
| F9.B | Médio | Falso positivo do microfone (Chrome tocando áudio de WhatsApp) — mitigado pelo início fraco em 20 s, pelo diálogo Sim/Não que apaga a gravação recusada e pela chave de desligamento |
| F9.C | Baixo | Só leitura e relatório |
| F9.D | Médio | Mutex nomeado é API Win32 — falha de criação cai para o comportamento antigo em vez de bloquear o app |
| F9.E | Baixo | Constante isolada com teste de regressão do hardware real |
