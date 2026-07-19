# Concept — Transkriptor v1.2

**Data:** 2026-07-08  
**Status:** Aprovado para implementação  
**Predecessor:** v1.1 (`docs/sdd/`)

---

## North Star

> Um profissional instala o Transkriptor, entra em reuniões o dia inteiro, e ao final do dia **confia** que tudo foi transcrito, analisado e está seguro — sem surpresas, sem cliques extras, sem dados na nuvem.

## Contexto

A v1.1 entregou a refatoração estrutural (config centralizado, debounce Meet, WAV em disco,
watchdog, assistente web, notificações). A **auditoria sênior de 2026-07-08** identificou
lacunas entre spec e implementação, um **bug crítico** no assistente, vulnerabilidades de
segurança locais, UX incompleta e **zero testes automatizados**.

A v1.2 fecha esse gap: produto confiável para uso diário profissional.

## Problema que a v1.2 resolve

| Dor | Evidência na auditoria |
|-----|------------------------|
| Assistente não abre na 1ª tentativa | `app.run()` depois do health check |
| Usuário não sabe se houve erro | Ícone vermelho nunca ativa |
| Regressões invisíveis | Nenhum `pytest` no repo |
| Dados sensíveis expostos | Path traversal na API Flask |
| Spec UX incompleta | Toasts ao vivo, UX-05 parcial, menu config ausente |
| Instalação frágil | `pythonw` hardcoded no `instalar.bat` |

## Solução v1.2 (em uma frase)

Corrigir P0, cobrir com testes, completar UX/spec pendente, endurecer segurança local e
estabelecer gates de qualidade por fase.

## Personas (inalteradas da v1.1)

- **Ana** — quer zero configuração e feedback claro.
- **Carlos** — exige privacidade; transcrições não podem vazar para outros processos.

## Princípios v1.2

1. **Evidência antes de done** — nenhuma fase fecha sem gate de testes verde.
2. **TDD obrigatório** — teste falha → implementa → passa (skill superpowers).
3. **Correção imediata** — gate falhou → `systematic-debugging` → fix → re-gate.
4. **Rastreabilidade** — todo requisito tem ID; toda tarefa referencia IDs.
5. **YAGNI** — RAG/chunking Ollama e suporte Teams ficam na Fase 6 (backlog), não bloqueiam P0.

## Escopo v1.2

### Dentro

- Infraestrutura pytest + gates por fase
- Correções P0/P1 da auditoria
- Completar UX-01, UX-05, UX-06 pendentes
- Segurança API (path traversal, XSS, token opcional)
- Mutex instância única, log rotation, GPU configurável
- `.gitignore`, script de verificação local
- **Criptografia em repouso** (Fase 3): arquivos `.tkpt` legíveis só pelo app
- **Identificação da voz do usuário** (Fase 7): cadastro + mic + rótulo `VOCÊ`
- **Nomes no Meet** (Fase 8): extensão Chrome estilo Tactiq (legendas CC)
- **Menu de opções completo** na bandeja (Fase 4)

### Fora (v1.3+)

- Suporte Microsoft Teams / Zoom
- Criptografia de pasta `transcricoes/`
- CI GitHub Actions (repo ainda sem git — preparar estrutura apenas)
- App installer MSI

## Métricas de sucesso v1.2

| Métrica | Alvo |
|---------|------|
| Assistente abre na 1ª tentativa | 100% em 10 execuções consecutivas |
| `pytest` | 100% verde no gate de cada fase |
| Path traversal | 0 leituras fora de `transcricoes/` |
| RAM reunião 1h | < 80 MB (medido em teste de integração leve) |
| Ícone de erro visível | Ativa em erro crítico e reverte após 30s |
| Identificação "VOCÊ" | ≥ 80% dos trechos falados pelo usuário (com mic ativo) rotulados corretamente em teste controlado |

---

## Identificação da sua voz (Fase 7)

### O que é possível

O Transkriptor hoje captura **loopback** (áudio que sai do alto-falante). Na maioria
dos Meets, **a sua voz não passa pelo alto-falante** — ela vai direto do microfone para
os outros participantes. Por isso, **só o loopback não basta** para saber o que *você* falou.

### Solução v1.2 (viável e local)

1. **Cadastro de voz (uma vez)** — você grava ~20s pelo microfone; o app salva um
   *embedding* ECAPA (mesmo modelo da diarização) em disco, só no seu PC.
2. **Captura dupla na reunião** — loopback (outros) + microfone (você), sincronizados.
3. **Identificação pós-reunião** — na diarização, o cluster mais parecido com seu perfil
   vira `VOCÊ` (ou o nome que você configurar); trechos do mic confirmam/reforçam o rótulo.
4. **Saída** — `transcricao_*_diarizado.txt` com linhas como:
   `[VOCÊ 02:15-02:22] Preciso validar o prazo até sexta.`

### Limitações honestas

- Sem cadastro de voz → continua `FALANTE_00`, `FALANTE_01`, etc.
- Headset com cancelamento agressivo ou mic mudo no Meet → pode não detectar você.
- Não é reconhecimento de identidade forense; é similaridade acústica com limiar configurável.
- Perfil de voz fica em `_modelo_voz/perfil_usuario.npz` — nunca sai da máquina.