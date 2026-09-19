# Evidências do diagnóstico

Inspeção iniciada em 18/09/2026 e consolidada em 19/09/2026. Os resultados abaixo são registros da execução desta análise, não reprodução dos números históricos da memória.

## Estado de referência

- `git rev-parse HEAD`: `eff83a61f3ee2291e48a80a00da3f70f1475ccbc`.
- `git status --short --branch` antes dos documentos: `## master...origin/master`, sem alterações locais.
- `config.VERSAO` e `pyproject.toml`: `1.7.0`.
- Python da suíte: 3.12.10; pytest 9.1.1.
- Pacotes observados: websockets 16.0; Flask 3.1.2; soundcard 0.4.6; numpy 2.4.2; faster-whisper 1.1.1; torch 2.11.0+cu128; speechbrain 1.1.0; cryptography 49.0.0. Inventário não equivale a verificação de CVEs.

## Testes existentes

Comando executado, exit 0:

```powershell
python -m pytest tests/ -q --tb=short
```

Resultado: `520 passed in 120.59s (0:02:00)`.

Isso cobre a suíte existente; não valida automaticamente os comportamentos novos propostos, o JavaScript no Chrome/Edge, atribuição nominal real nem inteligibilidade do áudio.

## Dependências do ambiente

`python -m pip check`, executado separadamente, exit 1:

```text
pdfplumber 0.11.10 requires pdfminer-six, which is not installed.
pdfplumber 0.11.10 has requirement Pillow>=12.2.0, but you have pillow 12.1.0.
```

`pdfplumber` não é dependência declarada do produto. Resultado aponta contaminação do ambiente global, não falha de execução comprovada do Transkriptor. Não foram instalados/removidos pacotes.

## Provas isoladas com dados sintéticos

As funções de `meet_bridge` e `correlacionador` foram chamadas sem servidor, captura ou acesso a dados reais:

```text
eventos_enviados: 600
eventos_retidos: 500
ultimo_ts_ms: 748500
origin_meet_aceita: False
origin_prefixo_indesejado (http://localhost.example.test): True
```

O ensaio inseriu eventos a cada 1.500 ms sem drenar. Confirmou descarte dos 100 finais.

Entrada da correlação: segmento `VOCÊ`, 0–1 s, texto sintético `alpha beta`; evento de legenda a 0,5 s, nome `Pessoa remota`, texto `gamma delta`. Saída observada: `Pessoa remota`, 0–1 s, `alpha beta`. Logo, legenda sem correspondência lexical ainda vence pelo fallback temporal.

Esses ensaios demonstram o comportamento das funções, não a origem emitida por um navegador nem a precisão em reunião real.

## Observação operacional mínima

Consulta de processos encontrou uma instância `pythonw.exe` cujo comando referencia Transkriptor. Consulta de listeners observou `127.0.0.1:5051` no PID 16412 e Ollama em `127.0.0.1:11434`, PID 88140. PIDs são efêmeros. Não foi estabelecido que a instância carregou o mesmo HEAD, que a extensão está conectada ou que existe reunião ativa. Nenhum processo foi encerrado.

## Não executados nesta análise

- Gates físicos de 25 s/600 s: acionam captura e foram reservados para implantação/validação consentida.
- Chamada real Chrome/Edge, OAuth Google, API REST autenticada, Meet Media API.
- Instalação limpa, benchmark de recursos, WER/DER e precisão nominal.
- Auditoria de ACLs, dependências transitivas por CVE e binários/modelos.
- Implementação das 28 tarefas; todos seus testes são futuros.

## Procedimento adotado

Instruções locais `using-superpowers`, `writing-plans`, `systematic-debugging` e `verification-before-completion`; auditoria de segurança baseada em fontes, com revisão independente de arquitetura. A revisão sistemática foi usada para localizar causas e contraprovas, sem implementar correções. Memória anterior serviu apenas para orientar os pontos de regressão; contagem histórica de testes não foi usada como estado atual.

## Verificação da entrega documental

- 28 IDs de tarefa únicos, 28 requisitos correspondentes, 28 testes finais e 28 critérios de aceite; zero tarefas marcadas como implementadas.
- Links relativos dos onze documentos principais verificados sem destino ausente. Os novos testes citados são entregáveis futuros, não arquivos preexistentes.
- Para execução por outra LLM foram acrescentados `interfaces.md` e `executor-llm.md`: assinaturas estáveis, ownership de módulos, decisões técnicas fechadas, ordem exata, limites de autorização, estado de task, algoritmo RED→GREEN, formato de evidência e condições de parada.
- As 16 decisões apresentadas ao usuário foram confirmadas e consolidadas em `decisoes-usuario.md`. O tipo/edição da conta Google continua factual e não informado; foi convertido em bloqueio exclusivo de H, sem impedir A–G.
- Verificação posterior à incorporação das decisões: 11 documentos Markdown principais; 28 tasks únicas; 28 requisitos rastreados; 16 decisões aprovadas com mapa de implementação; zero placeholders, links relativos quebrados, fences ímpares ou whitespace final.
- Regressão documental executada após as alterações: `python -m pytest tests/test_gitignore_docs.py tests/test_versao.py -q --tb=short` → 10 passed.
- A revisão de dependências eliminou APIs provisórias: `ArtifactRef` nasce em B2 antes do `EventStore`; `audio_reader.py` nasce em C2 antes da ampliação de streaming em C3; Native Messaging ficou explicitamente fora da v1.8; H3 recebeu casos RED documentais.
- O áudio longo protegido foi fechado como TKAS/1 sobre PyNaCl/Libsodium SecretStream, com formato e falhas definidos em `interfaces.md`. A primitiva foi escolhida após consulta à documentação oficial; implementação e compatibilidade Windows continuam futuras em E1/G1.
- Auditoria de segurança finalizada e indexada em 19/09/2026: dois achados de severidade baixa, validados por rastreamento de código; cobertura declarada parcial. Os ensaios sintéticos da ponte/correlação não foram usados como prova de exploração desses achados.
- O relatório e os JSONs canônicos foram copiados sem alteração para `seguranca/`, com igualdade de SHA-256 verificada em relação aos originais gerados. Checkpoints e exportação SARIF acompanham o pacote.
- Os digests de checkpoints foram conferidos com o leitor oficial da ferramenta: 4/4 válidos. Esses digests são do JSON normalizado, não do arquivo bruto; a comparação inicial de bytes com esse campo foi inadequada e foi substituída pela validação semântica. As cópias permanecem idênticas aos arquivos originais.
- A ferramenta avisou que o working tree mudou durante a auditoria. As mudanças são a documentação desta proposta; o relatório continua vinculado ao HEAD examinado, não a uma implementação das correções.
- Não houve modificação de código de produto, commit, push, instalação ou alteração de dados privados.
