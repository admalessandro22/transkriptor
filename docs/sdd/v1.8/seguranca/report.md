# Security Review: transkriptor

## Scope

Diagnostico read-only dos principais fluxos no HEAD eff83a61; cobertura parcial do inventario total.

- Scan mode: repository
- Target kind: git_revision
- Target ID: target_sha256_4e4497e9845a6be677a838400b1b776a31783a55125e71084a77d244bfd268c7
- Revision: eff83a61f3ee2291e48a80a00da3f70f1475ccbc
- Inventory strategy: repository
- Included paths: .
- Excluded paths: none
- Runtime or test status: Somente observacao minima de processos/listeners; sem captura ou reinicio.
- Artifacts reviewed: app_ciclo_reuniao.py, app_processamento.py, fila_processamento.py, processador_reuniao.py, transcricao_core.py, retranscritor.py, crypto_storage.py, identificador_voz.py, meet_bridge.py, extension/meet/content.js, assistente.py, assistente_ollama.py

Limitations and exclusions:
- Dois revisores independentes atingiram limite antes do recibo final; principal conferiu os achados aproveitados.
- Sem acesso Daybreak, auditoria CVE, ACL, pentest ou gate fisico.
- Nenhum dado privado de reuniao, biometria ou credencial inspecionado.
- Excluded transcricoes/: Dados privados do usuario, nao inspecionados.
- Excluded _modelo_voz/: Modelos e biometria privados, nao inspecionados.
- Excluded config_user.json: Preferencias e credenciais privadas, nao inspecionadas.

### Scan Summary

| Field | Value |
| --- | --- |
| Scan outcome | completed |
| Reportable findings | 2 |
| Severity mix | low: 2 |
| Confidence mix | high: 2 |
| Coverage | partial |
| Validation mode | Source review and existing pytest suite; synthetic bridge/correlation checks. |

Canonical artifacts: `scan-manifest.json`, `findings.json`, and `coverage.json`. This report is a deterministic projection of those files.

## Threat Model

Transkriptor e um aplicativo Windows local de captura loopback/mic, transcricao Whisper, diarizacao e assistente Flask/Ollama. A confianca atravessa pagina/extensao, listener autenticado, arquivos locais e processos worker. Processos do mesmo usuario nao constituem sandbox isolado.

### Assets

- Audio e transcricoes de reunioes
- Nomes, roster e embeddings biometricos
- Tokens da ponte e assistente, chave DPAPI
- Integridade dos jobs e disponibilidade da captura

### Trust Boundaries

- Pagina Meet/content script -\> service worker/bridge local
- Cliente HTTP -\> Flask em 127.0.0.1 com token
- Disco/backup -\> arquivos cifrados com chave protegida por DPAPI do usuario
- Capturador -\> fila JSON -\> worker com mesmos privilegios
- Texto transcrito nao confiavel -\> prompt Ollama local

### Attacker Capabilities

- Controlar conteudo falado/nome exibido numa reuniao
- Enviar requisicoes locais ou de pagina maliciosa, ainda sujeito a token/origem
- Obter copia de arquivos sem a chave, conforme ACL/backup; nao presumir esse acesso existente

### Security Objectives

- Consentimento antes de captura e coleta de conteudo
- Nao degradar protecao solicitada silenciosamente
- Conter paths e exigir autenticacao nos servicos
- Isolar identidade/eventos/contexto por reuniao
- Preservar audio e recuperar jobs sem duplicacao

### Assumptions

- TXT legivel e escolha explicita existente, nao promessa de cifra integral.
- DPAPI user-scope nao protege de todo processo com a mesma identidade.
- Worker nao e sandbox; Ollama configurado localmente.
- Modelos podem exigir download no setup; runtime local nao significa instalacao offline.
- Standalone/CLI diferem do tray em autenticacao e protecao; ponte inicia apesar de divergencia de documentacao.
- ACLs, extensao realmente instalada, Google/OAuth, binarios e CVEs nao verificados.

## Findings

| Finding | Severity | Confidence | Detailed write-up |
| --- | --- | --- | --- |
| [Falha de chave permite salvar audio e perfil de voz sem a protecao solicitada](#finding-1) | low | high | inline below |
| [Queda durante captura ou diarizacao deixa WAV fora da recuperacao de orfaos](#finding-2) | low | high | inline below |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct evidence supports the finding with no material unresolved blocker. |
| medium | Evidence supports a plausible issue, but material runtime or reachability proof remains. |
| low | Evidence is incomplete and the item is retained only for explicit follow-up. |

<a id="finding-1"></a>

### [1] Falha de chave permite salvar audio e perfil de voz sem a protecao solicitada

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | Branches e sinks de persistencia inspecionados diretamente; ACLs e frequencia da falha nao foram medidas. |
| Category | sensitive-data-exposure |
| CWE | CWE-636, CWE-312 |
| Affected lines | identificador_voz.py:22-51, crypto_storage.py:403-431 |

#### Summary

Ao salvar biometria ou finalizar WAV com criptografia ativa, a indisponibilidade da chave pode selecionar persistencia legivel. Um leitor de copia de disco/backup dispensa a chave DPAPI para esses artefatos. Nao implica exposicao remota nem abrange o TXT legivel intencional.

#### Root Cause

A politica de confidencialidade e a disponibilidade da chave sao reduzidas ao mesmo booleano. O caminho de perfil seleciona np.savez quando esse booleano e falso; a finalizacao de WAV retorna o original quando chave/cifra falham. Falta um estado obrigatorio de protecao pendente que os consumidores e a interface respeitem.

**Chave indisponivel equivale a cifra desativada** — `identificador_voz.py:22-28`

A decisao combina preferencia e capacidade. O chamador nao distingue usuario que desativou a protecao de falha ao acessar a chave.

```python
def _usar_criptografia_voz() -> bool:
    try:
        from crypto_storage import chave_disponivel, criptografia_ativa

        return criptografia_ativa() and chave_disponivel()
    except Exception:
        return False
```

**Persistencia plaintext do perfil** — `identificador_voz.py:47-51`

Se a decisao anterior e falsa, o embedding e salvo em NPZ sem cifra. O atacante considerado nao controla o embedding; seu pre-requisito e obter acesso a uma copia do arquivo.

```python
    np.savez(
        path,
        embedding=embedding.astype(np.float32),
        versao=np.int32(1),
    )
```

**WAV permanece legivel quando a chave falta** — `crypto_storage.py:412-413`

A finalizacao devolve o caminho WAV original sem sinalizar uma falha de protecao ao chamador.

```python
    if not (criptografia_ativa() and chave_disponivel()):
        return caminho
```

**Erro de cifragem tambem devolve WAV** — `crypto_storage.py:429-431`

O warning preserva o audio, o que e correto para recuperacao, mas o retorno nao distingue protecao aplicada de falha.

```python
    except Exception:
        logger.warning("Falha ao criptografar WAV %s", path.name, exc_info=True)
        return caminho
```

#### Validation

Conferidos preferencia/chave, desvio para escrita NPZ e retornos WAV. O sink legivel e determinado pelos branches; nao foi simulada falha DPAPI no perfil real.

Validation method: static source trace

Assertions:
- Criptografia ativa com chave indisponivel faz _usar_criptografia_voz retornar False.
- O caminho False persiste embedding sem cifragem.
- Falha de cifra WAV preserva caminho original sem resultado tipado de erro.

Limitations:
- Sem leitura de perfis, audio ou chaves privados.
- ACLs e acesso de terceiros a backups nao verificados.

#### Dataflow

Preferencia ativa + chave indisponivel -\> ramo sem protecao -\> NPZ/WAV legivel -\> leitor de copia

- **Source:** operacao legitima de persistencia durante falha de chave

- **Sink:** arquivo legivel no disco

- **Outcome:** confidencialidade em repouso nao aplicada

#### Reachability

Depende de acesso aos arquivos e da condicao de falha; nao existe bypass de token demonstrado.

- **Attacker:** leitor nao autorizado de copia de disco, backup ou pasta

- **Entry point:** copia do artefato persistido

- **Outcome:** leitura sem a chave de cifragem

Limitations:
- DPAPI nao promete isolamento contra todos os processos do mesmo usuario.
- TXT intencional nao constitui este achado.

#### Severity

**Low** — Exige falha de protecao e acesso independente aos arquivos; nao foi demonstrado acesso remoto. Prioridade de produto P1 por sensibilidade e estado pouco visivel.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** medium
- **Why:** Audio e biometria podem conter dados sensiveis.

Likelihood assessment:
- **Level:** low
- **Why:** Pre-requisitos locais e condicao de falha nao quantificados.

#### Remediation

Separar politica de capacidade; retornar erro/estado protection_pending obrigatorio e visivel quando protecao solicitada falhar. Para perfil novo, nao salvar plaintext; para audio ja capturado, preservar unica copia em area restrita para recuperacao, sem anunciar protecao concluida.

Tests:
- Com cifra ativa e chave indisponivel, salvar_perfil deve falhar explicitamente sem criar NPZ legivel.
- Erro ao cifrar WAV preserva original e marca protection_pending; sucesso so apos validar copia equivalente.
- Modo compativel preserva TXT intencional e informa a politica.

<a id="finding-2"></a>

### [2] Queda durante captura ou diarizacao deixa WAV fora da recuperacao de orfaos

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | Locais de escrita, limpeza normal e escopo limitado de recuperacao confirmados no codigo; crash real nao foi induzido. |
| Category | sensitive-data-exposure |
| CWE | CWE-459, CWE-312 |
| Affected lines | transcricao_core.py:173-178, retranscritor.py:245-253, crypto_storage.py:434-442 |

#### Summary

Captura escreve WAV na raiz de saida; diarizacao recria audio em pasta diarizacao_\*. Encerramento abrupto pode deixar esses arquivos legiveis, enquanto a recuperacao inspeciona somente \*.wav de PASTA_AUDIO. Exposicao exige acesso independente aos arquivos.

#### Root Cause

Escritores de audio usam locais diferentes do dominio da recuperacao. A captura e a diarizacao podem deixar WAVs fora de PASTA_AUDIO; a limpeza depende da saida normal e a retomada nao inventaria esses locais. Falta ownership por sessao e registro de todos os artefatos recuperaveis.

**WAV ativo ao lado da saida** — `transcricao_core.py:173-178`

A captura precisa preservar frames, mas os arquivos ativos ficam fora do diretorio audio varrido na recuperacao.

```python
        base = os.path.splitext(self._caminho_saida)[0]
        self._caminho_wav = base + "_audio.wav"
        self._wav = self._abrir_wav(self._caminho_wav)
        if self.capturar_mic:
            self._caminho_wav_mic = base + "_mic.wav"
            self._wav_mic = self._abrir_wav(self._caminho_wav_mic)
```

**Copia legivel para diarizacao** — `retranscritor.py:245-253`

TemporaryDirectory remove no encerramento normal; morte abrupta do processo pode impedir sua limpeza. Audio previamente decifrado volta a existir como WAV.

```python
        with tempfile.TemporaryDirectory(prefix="diarizacao_", dir=pasta) as tmp_dir:
            temporario_txt = Path(tmp_dir) / f"{base}.txt"
            temporario_wav = Path(tmp_dir) / f"{base}_audio.wav"
            temporario_txt.write_text(texto_final, encoding="utf-8")
            with wave.open(str(temporario_wav), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes((audio * 32767).astype(np.int16).tobytes())
```

**Recuperacao limitada a um nivel de PASTA_AUDIO** — `crypto_storage.py:434-442`

A varredura nao alcanca os arquivos na raiz nem os temporarios aninhados. Nao ha necessidade de o atacante controlar o caminho: ele precisa obter o arquivo residual.

```python
def recuperar_orfaos_wav(pasta_audio: str) -> int:
    """Criptografa WAVs plaintext órfãos em PASTA_AUDIO (recuperação pós-crash)."""
    if not (criptografia_ativa() and chave_disponivel()):
        return 0
    pasta = Path(pasta_audio)
    if not pasta.is_dir():
        return 0
    n = 0
    for wav in sorted(pasta.glob("*.wav")):
```

#### Validation

Conferidos os caminhos ativos e temporarios e a varredura glob nao recursiva usada na recuperacao. A garantia de limpeza normal nao cobre morte abrupta.

Validation method: static source trace

Assertions:
- Diarizacao grava WAV plaintext temporario mesmo ao processar fonte cifrada.
- Recuperacao atual nao abrange todos os caminhos de escrita.

Limitations:
- Nenhum processo real foi morto e nenhum audio privado foi aberto.
- ACLs e residuos existentes nao foram inventariados.

#### Dataflow

Audio capturado/decifrado -\> WAV ativo/temporario -\> crash -\> residuo nao recuperado

- **Source:** audio legitimo em processamento

- **Sink:** WAV residual fora de PASTA_AUDIO

- **Outcome:** persistencia legivel alem do ciclo esperado

#### Reachability

Requer acesso independente ao disco e encerramento abrupto; nao foi demonstrado ataque remoto.

- **Attacker:** leitor nao autorizado de arquivo/backup

- **Entry point:** arquivo residual apos crash

- **Outcome:** audio recuperavel sem chave

Limitations:
- Saida normal limpa TemporaryDirectory.
- Nao se recomenda apagar a unica fonte para corrigir confidencialidade.

#### Severity

**Low** — Falha requer interrupcao abrupta e leitor com acesso ao disco; nao foi demonstrada exposicao pela rede.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** medium
- **Why:** Audio integral pode permanecer disponivel.

Likelihood assessment:
- **Level:** low
- **Why:** Crash e acesso a arquivos sao pre-requisitos.

#### Remediation

Inventariar artefatos em armazenamento restrito por sessao, com lease, protecao e recuperacao de raiz legada/temporarios. Nao tocar sessoes vivas nem apagar unica copia; preferir processamento sem temporario plaintext quando viavel.

Tests:
- Interromper subprocesso de teste em pontos controlados e verificar recuperacao de todos os WAVs de sua sessao.
- Recuperacao nao altera sessao viva nem arquivos fora dos alvos permitidos.
- Falha de protecao preserva fonte e comunica estado pendente.

## Reviewed Surfaces

| Surface | Risk Area | Outcome | Notes |
| --- | --- | --- | --- |
| Criptografia e ciclo de vida de audio/biometria | not recorded | Reported | Dois achados locais de confidencialidade validados por rastreamento de fonte; ACLs e crash real pendentes. |
| Extensao Meet e correlacao | not recorded | Needs follow-up | Falhas funcionais confirmadas no handoff ao worker e correlacao; Origin isolado nao prova bypass de token. |
| API Flask e Ollama | not recorded | Needs follow-up | Token e realpath presentes; ausencia de isolamento de historico entre transcricoes e limites tipados sao melhorias. |

## Open Questions And Follow Up

- Handshake real Chrome/Edge e instalacao da extensao nao exercitados.
- ACLs, contas Google e vulnerabilidades de dependencias por CVE nao verificadas.
- Nem todos os arquivos auxiliares/legados foram auditados integralmente.
- Dois revisores independentes atingiram limite de uso antes de entregar cobertura final; seus avisos foram conferidos pelo agente principal.
  - Follow-up prompt: Review deferred unit deferred-7ef6af5ffc62439e and close its stated proof gap.
