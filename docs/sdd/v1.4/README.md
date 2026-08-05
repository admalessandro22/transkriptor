# SDD v1.4 — Transkriptor

Versão **em execução** (fonte de verdade). Nasceu de um relato simples:
o app abria, ia para a bandeja e nunca gravava nada.

A auditoria encontrou **duas falhas silenciosas simultâneas**:

1. **A captura de áudio estava quebrada** — `soundcard 0.4.3` com `numpy 2.4.2`
   levanta `ValueError` em toda leitura, e o laço de captura engolia a exceção.
   Evidência: todos os áudios salvos tinham 77 bytes (cabeçalho WAV vazio).
2. **O detector não reconhecia mais o Google Meet** — o regex esperava o formato
   legado `<sala> - Google Meet`; o Meet hoje usa `Meet – abc-defg-hij`.

Ordem de leitura:

1. `concept.md` — a investigação, as causas raiz e as decisões de projeto.
2. `spec.md` — requisitos `FR-9.*` / `NFR-9.*` / `UX-9.*`.
3. `plan.md` — ordem das fases, gates e rollback.
4. `tasks.md` — tarefas e o que já foi verificado.

## Novos módulos

| Módulo | Papel |
|--------|-------|
| `deteccao_reuniao.py` | Fusão OR de fontes independentes com debounce assimétrico |
| `monitor_microfone.py` | "Quem está usando o microfone agora", pelo registro do Windows |
| `diagnostico.py` | Responde "por que não está gravando?" em uma tela |

## Mudança de comportamento observável

| Antes | Depois |
|-------|--------|
| Não detectava reuniões do Meet atual | Detecta em ~10 s, também Zoom |
| Trocar de aba encerrava a gravação em 15 s | A gravação continua (microfone segura o sinal) |
| Falha de áudio invisível | Erro crítico no ícone + toast + Diagnóstico |
| Sem forma de investigar | Menu → Diagnóstico com relatório completo |
| GTX 1650 caía em `small`/CPU | Usa `medium`/CUDA como a spec v1.3 pedia |
