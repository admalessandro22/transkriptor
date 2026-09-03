# Concept — Transkriptor v1.5

## Incidente observado

Em 2026-08-06, uma transcrição manual permaneceu ativa de 09:31 até 16:43.
Ela uniu duas reuniões e continuou capturando sons alheios, inclusive áudio do
WhatsApp. O processo carregado era a v1.3, embora os arquivos da v1.4 já
estivessem no disco.

Evidências locais, sem registrar conteúdo falado:

- um processo `pythonw.exe` iniciado em 2026-07-21 permaneceu carregado após a
  atualização de 2026-08-04;
- 257 notificações foram disparadas em um dia, próximas da cadência dos blocos
  de 25 s;
- o processo chegou a aproximadamente 3,65 GB privados e mais de três núcleos
  de CPU durante a reunião;
- o loopback final tem 23.736 s, enquanto a sessão durou cerca de 25.965 s;
- a primeira reunião tem 5.825 s mapeados; a segunda, 2.175 s em uma janela de
  2.460 s, com perda estimada de 285 s;
- depois da segunda reunião, 5.411 s adicionais foram capturados indevidamente;
- o `.tkpt` final não abre porque a chave DPAPI mantida pelo processo antigo não
  permaneceu na configuração.

## Causas-raiz

1. **Modo manual sem limite:** ignora o fim detectado da reunião.
2. **Início por fonte fraca:** microfone sustentado pode virar reunião.
3. **Fim por OR irrestrito:** qualquer fonte fraca mantém a captura para sempre.
4. **Whisper ao vivo acoplado ao WAV:** quando a IA atrasa, a fila descarta áudio.
5. **Toast por trecho:** `plyer` cria um ícone temporário por notificação e o
   Windows acumula ícones-fantasma, som e piscadas.
6. **Código atualizado sem reinício:** o processo antigo continuou executando a
   versão carregada em memória.
7. **Configuração sobrescrita por snapshot:** uma gravação integral de JSON pode
   apagar uma chave criada por outro componente.
8. **Resultado não humano:** o texto só aparece depois do encerramento e, quando
   criptografado, não é legível diretamente na pasta.

## Decisão de arquitetura

Durante a reunião, o Transkriptor apenas captura áudio. Whisper, diarização e
modelos de voz são carregados por um trabalhador separado depois que a reunião
termina. A captura nunca depende da velocidade da IA.

O ciclo de vida passa a ser explícito:

```text
AGUARDANDO -> PEDINDO_CONSENTIMENTO -> GRAVANDO -> FINALIZANDO
     ^                  | Não/timeout                    |
     +------------------+                               v
     +------------- PRONTA <- PROCESSANDO <- EM_FILA ---+
```

Somente fonte forte inicia ou sustenta indefinidamente uma reunião: extensão do
Meet ou título inequívoco de chamada. Microfone é diagnóstico auxiliar; nunca
inicia e não impede o encerramento após a janela de graça sem fonte forte.

## Resultado do usuário

Cada reunião aceita produz `transcricao_<data>_<hora>.txt` em UTF-8, com
timestamps e, quando disponível, falantes. Uma cópia `.tkpt` pode ser mantida,
mas não substitui o `.txt`. O áudio fica separado e sujeito à retenção.

## Recuperação do incidente

O áudio original fica preservado até duas cópias de reunião serem extraídas e
retranscritas. O primeiro intervalo é aproximadamente `0..5825 s`; o segundo,
`16150..18325 s`. O segundo resultado deve carregar aviso de lacuna estimada de
285 s. Só depois da validação os artefatos combinados e a captura indevida podem
ir para a Lixeira.

