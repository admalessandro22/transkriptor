# Evidências — SDD v2.0

Uma evidência por task (`T-15.A1.md` … `T-15.F1.md`), uma por gate de fase (`F15.A-gate.md` …) e o `GATE-FINAL.md`.

Formato mínimo:

- requisito;
- SHA;
- comandos com contagens de testes;
- capturas sintéticas (nunca de reunião real);
- medidas (tempo, tamanho, precisão);
- o que **não** foi verificado e por quê.

Proibido incluir texto de legenda, nome real, chat, chave, token, caminho pessoal ou bytes capturados do Meet.

## Evidência do diagnóstico (29/09/2026)

- Tactiq `3.1.7049` examinada em `%LOCALAPPDATA%\Google\Chrome\User Data\Default\Extensions\fggkaccpbmombhnjkjokndojfgagejfb\3.1.7049_0`. A formatação foi feita numa pasta temporária fora do repositório, e nenhum arquivo da Tactiq foi versionado.
- Ollama desta máquina:
  - versão `0.34.4`;
  - executável em `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`;
  - chave de desinstalação HKCU presente;
  - API em `127.0.0.1:11434` com 3 modelos;
  - `OLLAMA_HOST` não definido.
