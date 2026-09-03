# Plan — Transkriptor v1.5

Ordem fechada. Uma fase só começa com a anterior verde e commitada.

```text
F10.A configuração/chave
  -> F10.B detecção estrita
    -> F10.C consentimento/notificações
      -> F10.D captura sem IA
        -> F10.E fila/processamento/texto
          -> F10.F integração/recursos
            -> F10.G recuperação
              -> F10.H auditoria final
```

## Regra por tarefa

1. Escrever teste RED citando o ID da spec.
2. Rodar o teste e confirmar falha pelo motivo esperado.
3. Implementar a menor mudança coerente.
4. Rodar o teste específico ao final da tarefa.
5. Rodar o gate da fase quando for a última tarefa da fase.
6. Commit em português, imperativo, limitado à tarefa.

Falha de teste exige `superpowers:systematic-debugging`, correção da causa e nova
execução do mesmo gate antes de avançar.

## Gates

| Fase | Gate automatizado | Gate real |
|---|---|---|
| F10.A | `pytest tests/test_config_user_modulo.py tests/test_crypto_storage.py -v` | reiniciar app e reabrir `.tkpt` sintético |
| F10.B | `pytest tests/test_deteccao_multi_fonte.py tests/test_integracao_monitor_meet.py -v` | áudio fora de Meet não inicia |
| F10.C | `pytest tests/test_aviso_gravacao.py tests/test_notificador.py tests/test_bandeja_lifecycle.py -v` | uma pergunta, zero sons/ícones extras |
| F10.D | `pytest tests/test_gravacao_pos_reuniao.py tests/test_watchdog.py -v` | 10 min de WAV crescente sem IA importada |
| F10.E | `pytest tests/test_fila_processamento.py tests/test_processador_reuniao.py tests/test_retranscritor.py -v` | sair do Meet cria `.txt` |
| F10.F | `pytest tests/test_fluxo_reuniao_v15.py tests/test_limite_linhas.py -v` | processo/ícone/CPU/memória |
| F10.G | `pytest tests/test_recuperacao_audio.py -v` | dois `.txt` recuperados e originais preservados até aprovação |
| F10.H | `python scripts/verificar_fase.py --fase all` e `pytest tests/ -q` | checklist abaixo |

## Gate final Windows

1. Iniciar v1.5 e provar versão/PID únicos.
2. Tocar áudio local fora de reunião por 2 min: nenhum arquivo/job.
3. Simular/abrir Meet: pergunta aparece uma vez e sem som.
4. Responder Não: nenhum arquivo; responder Sim em nova sessão: grava.
5. Trocar de aba com extensão ativa: continua; encerrar/expirar extensão: para.
6. Durante gravação, provar que Whisper/modelos não estão carregados.
7. Depois do fim, provar job e `.txt`; abrir o texto sem expor conteúdo no log.
8. Reiniciar Explorer: um ícone. Reiniciar app: job pendente retoma.
9. Auditar os dois resultados recuperados e a lacuna da segunda reunião.

## Rollback

Cada tarefa é um commit. Reversão usa `git revert <sha>`; dados reais nunca são
apagados pelo rollback. Jobs desconhecidos permanecem preservados como `failed`.

