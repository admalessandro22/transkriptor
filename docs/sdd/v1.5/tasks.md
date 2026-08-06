# Tasks — Transkriptor v1.5

Status inicial: ⬜ pendente. Cada tarefa termina com o teste listado e commit.

| ID | Entrega | Spec | Teste obrigatório ao final | Status |
|---|---|---|---|---|
| T-10.A1 | persistência dedicada da chave e merge de config | SEC-10.F1/F2 | config + crypto | ⬜ |
| T-10.A2 | isolamento integral dos testes de estado local | SEC-10.F3 | testes de isolamento | ⬜ |
| T-10.B1 | microfone nunca inicia reunião | FR-10.A1/A3 | detecção multi-fonte | ⬜ |
| T-10.B2 | fim limitado sem fonte forte | FR-10.A2/A4 | detecção + integração | ⬜ |
| T-10.C1 | consentimento antes da captura e timeout negativo | FR-10.B1/B2/B3 | aviso de gravação | ⬜ |
| T-10.C2 | remover toast ao vivo e backend `plyer` | UX-10.B1/B2 | notificador + bandeja | ⬜ |
| T-10.D1 | modo de captura posterior sem Whisper | FR/NFR-10.C* | gravação posterior | ⬜ |
| T-10.D2 | flush, métricas e watchdog do modo leve | FR-10.C2/C3 | gravação + watchdog | ⬜ |
| T-10.E1 | fila durável atômica e retomada | FR-10.D1/D2/D4 | fila | ⬜ |
| T-10.E2 | subprocesso posterior e `.txt` atômico | FR-10.D3, FR-10.E* | processador + retranscritor | ⬜ |
| T-10.F1 | integrar ciclo completo no app/menu | FR-10.A4, FR-10.E4 | fluxo v1.5 | ⬜ |
| T-10.F2 | versão, manual e gates de recursos | NFR-10.C*, H1 | versão/manual/recursos | ⬜ |
| T-10.G1 | extrator genérico e seguro de intervalos | FR-10.G1 | recuperação | ⬜ |
| T-10.G2 | recuperar e retranscrever as duas reuniões | FR-10.G2/G3 | auditoria de artefatos | ⬜ |
| T-10.H1 | auditoria final de qualidade/coerência/segurança | NFR-10.H* | suíte + Windows + diff | ⬜ |

Nenhuma tarefa pode ser marcada ✅ apenas porque o código existe. O teste final
da linha, o commit e a evidência correspondente precisam existir.

