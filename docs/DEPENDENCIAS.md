# Dependências — matriz validada (T-13.G1)

Instalação limpa por rota; semiwindows global nunca é "consertado" pelo
instalador. O núcleo é idêntico nas duas rotas; só o casal torch/torchaudio
diverge (índice PyTorch cu128 na rota CUDA).

| Rota | Trava | Prova |
|---|---|---|
| CPU | `requirements/constraints-cpu.txt` | CI Windows (`tests.yml`) + pré-checagem |
| CUDA 12.8 | `requirements/constraints-cuda.txt` | Máquina local (CUDA 12.8, torch 2.11.0+cu128, suíte verde) |

Uso:

```bat
REM CPU
.venv\Scripts\python.exe -m pip install -r requirements.txt -c requirements\constraints-cpu.txt
REM CUDA
.venv\Scripts\python.exe -m pip install -r requirements.txt -c requirements\constraints-cuda.txt
```

O `instalar.bat` detecta a GPU, valida a combinação
(`instalar_helper.py --check deps --rota cpu|cuda`, falha clara se
incompatível) e instala com a trava da rota.

## Pinos relevantes

- `websockets==16.0` (API `max_size`/serve usada pela ponte; CI prova).
- `torch==2.11.0` / `torchaudio==2.11.0` (CPU) e `+cu128` (CUDA).
- `PyNaCl==1.6.2` (wheel `cp38-abi3-win_amd64` com libsodium embutido; sem ele,
  áudio longo protegido bloqueia com erro explícito — sem cifra alternativa).
- `soundcard>=0.4.6` (anteriores quebram com numpy 2.x).
- `cryptography==49.0.0` (AES-GCM + HKDF do TKAS/1).

## SBOM e CVEs

- `docs/sbom.json`: inventário gerado do ambiente validado
  (`importlib.metadata`, sem credenciais). Regenerar após trocar pinos.
- CVEs: sem advisory aberto para o conjunto pinado na data desta tarefa;
  revalidar via GitHub Advisory/OSV antes de cada release. Pacote vulnerável
  só entra com justificativa específica e prazo (registrar aqui).

## Modelos (licenças)

- Whisper (faster-whisper/CTranslate2): conforme licença dos pesos escolhidos.
- ECAPA-TDNN via SpeechBrain: modelo público sem token; respeitar a licença
  da fonte (`MODELO_VOZ_FONTE`).
- Ollama/modelos locais: licença de cada modelo baixado.
