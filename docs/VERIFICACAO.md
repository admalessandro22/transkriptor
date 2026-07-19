# Verificação — Transkriptor v1.2

Comandos copy-paste para gates SDD por fase.

## Fase 0 — Fundação QA

```bash
python scripts/verificar_fase.py --fase 0
```

## Fase 1 — P0 Crítico

```bash
python scripts/verificar_fase.py --fase 1
```

## Fase 2 — Engenharia P1

```bash
python scripts/verificar_fase.py --fase 2
```

## Fase 3 — Criptografia em repouso

```bash
python scripts/verificar_fase.py --fase 3
```

## Fase 4 — UX Bandeja e Assistente

```bash
python scripts/verificar_fase.py --fase 4
```

## Fase 5 — Segurança Avançada

```bash
python scripts/verificar_fase.py --fase 5
```

## Fase 6 — Manutenção

```bash
python scripts/verificar_fase.py --fase 6
```

## Fase 7 — Identificação da Voz (VOCÊ)

```bash
python scripts/verificar_fase.py --fase 7
```

## Fase 8 — Nomes no Meet (opcional)

```bash
python scripts/verificar_fase.py --fase 8
```

Requer extensão Chrome em `extension/meet/` carregada em `chrome://extensions`.

## Gate final

```bash
python scripts/verificar_fase.py --fase all
```

## Suite completa

```bash
python -m pytest tests/ -v --tb=short
```

## v1.2.1 — Estabilidade da bandeja e Meet

- Data/hora: 2026-07-18, início da build final às 10:00:18 (America/Sao_Paulo)
- Windows: Microsoft Windows 11 Pro 64 bits, versão `10.0.22000`, build `22000`
- Navegadores instalados: Google Chrome `149.0.7827.201`; Microsoft Edge `150.0.4078.48`
- Python: `3.12.10`
- Processo validado: PID `4300`; mutex `transkriptor.lock` com PID `4300`
- Estado operacional de entrega: PID/mutex `51512`, um único ícone, preferência de Startup `false` e atalho de Startup ausente
- [x] Atalho real abre via `pythonw.exe`, sem console (`WindowStyle=7`).
- [x] Ícone fica pronto em 1,43 s, aparece uma vez e expõe o tooltip `Transkriptor 1.1 - Aguardando Meet`.
- [x] Menu real abre e expõe 18 itens, incluindo o estado dinâmico `Aguardando Google Meet...`.
- [x] Processo e ícone permaneceram por 30,27 min ociosos; PID/lock `4300` e tooltip foram reconfirmados às 10:32:06.
- [x] Janela Win32 com o título real `Daily - Google Meet - Google Chrome` solicita transcrição em aproximadamente 12 s.
- [x] Com `EXIGIR_JANELA_VISIVEL=False`, minimizar a janela por 10 s não encerra a reunião; a parada só ocorre depois de fechar e confirmar três ausências.
- [x] Fechar a janela do Meet finaliza após três ciclos de ausência e salva a transcrição.
- [x] Segunda abertura é bloqueada; o processo transitório sai e permanece somente o PID `4300`.
- [x] Reiniciar o Explorer preserva o processo e restaura um único ícone no overflow (validações `34404` → `39224` e `45456` → `22784`).
- [x] Preferência “Iniciar com o Windows” permaneceu `false`.
- Resultado: **APROVADO**.

### Atalho inspecionado

- Arquivo: `C:\Users\Alessandro Souza\Desktop\Transkriptor.lnk`
- Target: `C:\Users\Alessandro Souza\AppData\Local\Programs\Python\Python312\pythonw.exe`
- Arguments: `"C:\Projetos\transkriptor\transkriptor.pyw"`
- Working directory: `C:\Projetos\transkriptor`
- Icon: `C:\Projetos\transkriptor\transkriptor.ico`

### Gates automatizados da build final

```text
python scripts/verificar_fase.py --fase estabilidade  -> 27 passed
python -m pytest tests/ -q --tb=short                  -> 170 passed
python scripts/verificar_fase.py --fase all            -> 148 passed
```

### Evidência do log — somente mensagens de sistema

```text
2026-07-18 10:00:20,365 [INFO] Bandeja pronta.
2026-07-18 10:00:20,366 [INFO] Monitor do Meet iniciado.
2026-07-18 10:01:00,408 [INFO] Meet confirmado após 2 detecções.
2026-07-18 10:01:04,241 [INFO] Meet confirmado. Iniciando transcricao...
2026-07-18 10:01:21,685 [INFO] Meet encerrado após 3 ausências.
2026-07-18 10:01:22,389 [INFO] Transcrição encerrada.
2026-07-18 10:03:37,840 [INFO] Segunda instancia bloqueada pelo mutex.
2026-07-18 10:34:17,510 [INFO] Meet encerrado após 3 ausências.
```

## v1.3 — Fase 8 (refatoração final)

- Data: 2026-07-19
- T-F8-01: front do assistente em `templates/assistente.html`, `static/assistente.css`, `static/assistente.js`; Flask `render_template`; `assistente.py` < 300 linhas; cliente Ollama em `assistente_ollama.py`.
- T-F8-02: `transkriptor.pyw` reduzido a bootstrap + núcleo; `startup_windows.py` (PS1 parametrizado), `perfil_voz_flow.py`, `app_bandeja_menu.py`, `bandeja_icone.py`, `transkriptor_menu_flows.py`, `diarizacao_final.py`; fallback `win10toast` removido de `notificador.py`.
- Gate automatizado: `python -m pytest tests/ -q` → **256 passed** (1 warning de thread injetada no watchdog, esperado).
- Limite de linhas: todos os `*.py` / `*.pyw` de produção ≤ 500 (ver `lines-check.log`).
- Roteiro manual de release (plan.md): pendente de execução em reunião real de 10 min — registrar quando concluído.

