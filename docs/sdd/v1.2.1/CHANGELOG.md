# Changelog — Transkriptor v1.2.1

## Corrigido

- Registro do ícone somente após a prontidão do backend Win32 do `pystray`.
- Inicialização idempotente de uma única thread de monitoramento do Google Meet.
- Recuperação de mutex obsoleto quando o PID já terminou, mesmo que o handle Win32 ainda possa ser aberto.
- Detecção de títulos reais de reuniões no Google Chrome e Microsoft Edge, sem aceitar páginas de ajuda, busca ou tutorial.
- Integração testável entre detecção, início e encerramento automáticos da transcrição.
- Criação de um único atalho silencioso `Transkriptor.lnk` na Área de Trabalho.

## Desempenho

- O Whisper passou a ser carregado somente quando uma transcrição é solicitada; a bandeja ficou pronta em 1,43 s no gate Windows, contra cerca de 13 s antes da correção.

## Qualidade

- Testes de regressão do ciclo de vida e do startup da bandeja.
- Testes dos títulos de janela e do fluxo detector → transcrição.
- Inspeção automatizada dos metadados do `.lnk`.
- Gate `python scripts/verificar_fase.py --fase estabilidade`.
- Verificação real de mutex, atalho, Google Meet sintético, reinício do Explorer e restauração do ícone.
