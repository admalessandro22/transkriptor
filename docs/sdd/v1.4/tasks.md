# Tasks — Transkriptor v1.4

Uma tarefa = um commit. Status: ✅ concluída.

## F9.A — Captura de áudio confiável

| ID | Tarefa | Spec | Status |
|----|--------|------|--------|
| T-9.A1 | Pinar `soundcard>=0.4.6` e `numpy<3` em `requirements.txt` com o porquê no comentário | FR-9.A1 | ✅ |
| T-9.A2 | `audio_utils.diagnosticar_captura` (pura) + testes dos 4 casos | FR-9.A2 | ✅ |
| T-9.A3 | `audio_utils.testar_loopback` / `testar_microfone` que nunca levantam | FR-9.A3 | ✅ |
| T-9.A4 | Autoteste de áudio no startup com erro crítico visível | FR-9.A4 | ✅ |
| T-9.A5 | Teste de gate que falha se `soundcard`×`numpy` forem incompatíveis | FR-9.A1 | ✅ |

## F9.B — Detecção multi-fonte

| ID | Tarefa | Spec | Status |
|----|--------|------|--------|
| T-9.B1 | `detector_meet.classificar_titulo` com formato atual do Meet, Zoom e exclusão só no nomeado | FR-9.B3/B4/B5 | ✅ |
| T-9.B2 | `monitor_microfone.py` — leitura do ConsentStore e filtro de apps de conferência | FR-9.B6 | ✅ |
| T-9.B3 | `deteccao_reuniao.py` — `Sinal`, `FonteTitulo`, `FonteMicrofone`, `FontePonte`, `fundir` | FR-9.B1/B10 | ✅ |
| T-9.B4 | `DetectorReuniao` com debounce assimétrico | FR-9.B2 | ✅ |
| T-9.B5 | `MeetBridge.reuniao_ativa()` + heartbeat com expiração | FR-9.B7 | ✅ |
| T-9.B6 | Extensão: `emChamada()`, heartbeat de 5 s, `ativa:false` no unload | FR-9.B8 | ✅ |
| T-9.B7 | Ponte sempre ativa e tolerante a falha; app usa `DetectorReuniao` | FR-9.B9 | ✅ |
| T-9.B8 | Status do menu mostra as fontes ativas | UX-9.B1 | ✅ |

## F9.C — Autodiagnóstico

| ID | Tarefa | Spec | Status |
|----|--------|------|--------|
| T-9.C1 | `diagnostico.py` — checagens, resumo e relatório em texto | FR-9.C2/C3 | ✅ |
| T-9.C2 | Item de menu "Diagnóstico (por que não está gravando?)" | FR-9.C1 | ✅ |
| T-9.C3 | Heartbeat periódico do monitor no log | FR-9.C4 | ✅ |

## F9.D — Ciclo de vida

| ID | Tarefa | Spec | Status |
|----|--------|------|--------|
| T-9.D1 | Mutex nomeado do Windows + limpeza de lock órfão | FR-9.D1 | ✅ |
| T-9.D2 | `_em_thread` para início/fim fora do monitor | FR-9.D2 | ✅ |
| T-9.D3 | Portão atômico `_iniciando` | FR-9.D3 | ✅ |
| T-9.D4 | Diálogo de gravação com toast prévio e `argtypes` declarados | FR-9.D4 | ✅ |
| T-9.D5 | Opção "Perguntar antes de gravar" persistida | FR-9.D5 | ✅ |

## F9.E — Qualidade

| ID | Tarefa | Spec | Status |
|----|--------|------|--------|
| T-9.E1 | `VRAM_MIN_MEDIUM_GB = 3.8` + teste com o valor real da GTX 1650 | FR-9.E1 | ✅ |
| T-9.E2 | Suíte completa verde | NFR-9.E1 | ✅ |
| T-9.E3 | Manual do usuário: seção de diagnóstico e detecção | — | ✅ |

## Verificação executada

- `python -m pytest tests/ -q` — 100% verde.
- **Áudio real:** fala sintetizada pelos alto-falantes → loopback → Whisper →
  transcrição com o texto correto; WAV preservado com 544 KB (antes: 77 bytes).
- **Detecção real:** janela com título `Meet – abc-defg-hij - Google Chrome` lida
  por `pygetwindow` → `FonteTitulo` forte → `DetectorReuniao` retorna `iniciou`
  no 2º ciclo. O regex da v1.3 devolvia `False` para esse mesmo título.
- **Diagnóstico real:** relatório com 0 erros, três fontes listadas e
  `auto → medium em cuda` (antes: `small`/CPU por causa do limiar de VRAM).
