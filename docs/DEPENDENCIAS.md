# Dependências Windows/Python 3.12 (T-13.G1)

As entradas diretas ficam em `requirements/base.in`, `cpu.in`, `cuda.in` e
`dev.in`. Os `requirements-*.lock` fixam a árvore transitiva e o SHA-256 do
artefato Windows `cp312 win_amd64`. A rota CUDA muda apenas `torch` e
`torchaudio`. O instalador usa o lock de produção da rota; `requirements.txt`
fica apenas para compatibilidade histórica.

## Instalação e verificação

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements\requirements-cpu.lock
.\.venv\Scripts\python.exe -m pip check

# CUDA, em venv separada com driver compatível:
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements\requirements-cuda.lock

# Somente CI/desenvolvimento:
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements\requirements-dev.lock
```

Não instalar CPU e CUDA na mesma venv. A instalação física CUDA continua
pendente até o gate de aceite; hashes publicados não provam essa instalação.
O instalador recusa uma `.venv` já preenchida com a outra rota e valida as
versões exatas de `torch`/`torchaudio` antes e depois de instalar. Ele preserva
a venv existente no erro; a troca de rota requer uma pasta de instalação nova.

## Regeneração dos locks

Executar em Windows/Python 3.12, em venv isolada com `pip-tools`:

```powershell
python -m piptools compile requirements/cpu.in --resolver=backtracking --allow-unsafe --output-file requirements/requirements-cpu.pins
python -m pip install --dry-run --ignore-installed --report requirements/report-cpu.json -r requirements/requirements-cpu.pins
python scripts/gerar_lock_windows.py requirements/requirements-cpu.pins requirements/report-cpu.json requirements/requirements-cpu.lock

python -m piptools compile requirements/dev.in --resolver=backtracking --allow-unsafe --constraint requirements/requirements-cpu.lock --output-file requirements/requirements-dev.pins
python -m pip install --dry-run --ignore-installed --report requirements/report-dev.json -r requirements/requirements-dev.pins
python scripts/gerar_lock_windows.py requirements/requirements-dev.pins requirements/report-dev.json requirements/requirements-dev.lock
```

O plano prescreve `pip-compile --generate-hashes`. A tentativa nessa matriz
enumerou wheels de outras plataformas e exigiu downloads grandes. Usamos a
resolução exata do `pip-compile` e os hashes dos artefatos Windows selecionados
pelo relatório do `pip`. O gerador recusa pinos ou hashes ausentes, duplicados
e árvore divergente. O lock CPU passou em `pip install --dry-run
--ignore-installed --require-hashes`.

O wheel CUDA de `torch` tem 2,7 GB; a geração com `pip-compile` foi interrompida
para preservar o processamento real do usuário e o espaço livre. A comparação
dos metadados Windows de `torch` e `torchaudio` CPU/CUDA mostrou a mesma árvore
Windows; os extras diferentes eram apenas Linux. Revalidar essa equivalência
ao atualizar PyTorch. Os hashes SHA-256 `cp312 win_amd64` foram conferidos nos
índices oficiais [torch cu128](https://download.pytorch.org/whl/cu128/torch/) e
[torchaudio cu128](https://download.pytorch.org/whl/cu128/torchaudio/):

```powershell
python -c "from scripts.gerar_lock_windows import gerar_cuda_de_cpu; gerar_cuda_de_cpu('requirements/requirements-cpu.lock', 'requirements/requirements-cuda.lock', '7c78215c3af4f62e63f2b2e360f1722fc719b0853c7ac22666483d9810613a4c', 'e0203d44b6dcf4c59f2ce38f997616e663b2a23a9e0b20ebb90ea0c787b5e86a')"
```

## SBOM, CVEs e modelos

`docs/sbom.json` é CycloneDX da venv CPU limpa, com dependências transitivas,
versões, licenças declaradas e SHA-256 do lock. Regenerar após trocar pinos:

```powershell
.\.venv\Scripts\python.exe scripts/gerar_sbom.py --python .venv\Scripts\python.exe --lock requirements\requirements-cpu.lock --output docs\sbom.json
.\.venv\Scripts\python.exe -m pip_audit -r requirements\requirements-cpu.lock
```

Auditoria em 23/09/2026: os pinos iniciais geraram 44 entradas (com IDs
duplicados) em cinco pacotes. Foram atualizados `cryptography` para 50.0.1,
`Flask` para 3.1.3 e `Pillow` para 12.3.0. A nova auditoria bruta apontou
somente três entradas em dois pacotes:

| Pacote | Advisory | Motivo da exceção temporária | Prazo |
|---|---|---|---|
| `setuptools==81.0.0` | [PYSEC-2026-3447](https://github.com/advisories/GHSA-h35f-9h28-mq5c) | afeta geração de sdist em macOS APFS/HFS+, não execução no Windows; `torch 2.11` exige `setuptools<82` | 15/10/2026 |
| `torch==2.11.0` | [PYSEC-2025-194](https://github.com/advisories/GHSA-rrmf-rvhw-rf47) | afeta `torch.jit.script` local; não há chamada direta no código do app; atualização para 2.13 exige nova matriz CPU/CUDA e gates reais | 15/10/2026 |

O CI audita todos os outros pacotes, ignora apenas esses dois IDs e falha
automaticamente após o prazo. Essa exceção é provisória e precisa de aceite
explícito antes de declarar a release pronta. O relatório JSON de CI mantém a
lista auditada para revisão. Atualizar a matriz ou remover as exceções antes
do prazo; nenhuma ausência de alerta deve ser inferida para os dois pacotes.

As licenças dos pesos de Whisper/faster-whisper, ECAPA-TDNN via
SpeechBrain (`MODELO_VOZ_FONTE`) e cada modelo Ollama baixado são verificadas
separadamente da licença dos wheels.
