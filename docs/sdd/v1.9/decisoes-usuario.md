# Decisões do usuário — SDD v1.9 (design)

Estado em 24/09/2026: **aprovadas.** O usuário aprovou a recomendação padrão de todas as decisões DP-14-01 a DP-14-11 e revisou a DP-14-12 (ver abaixo). A coluna "Recomendação" passa a ser a decisão vigente; a coluna "Padrão" fica como registro do que foi proposto.

| ID | Decisão pendente | Recomendação | Padrão se não houver resposta |
|---|---|---|---|
| DP-14-01 | Direção visual: (a) grafite + azul elétrico, (b) grafite + verde-azulado, (c) manter violeta/dourado atual | (a): sóbrio, tecnológico, contrasta com os estados semânticos | (a) |
| DP-14-02 | Tema: escuro apenas, claro apenas, ou ambos seguindo o Windows com alternância | Ambos; o produto convive com o tema do sistema | Ambos |
| DP-14-03 | Tipografia: fontes do sistema (Segoe UI Variable) ou fonte própria embarcada (Inter, licença OFL, +400 KB) | Sistema: zero rede, CSP simples, aparência nativa no Windows 11 | Sistema |
| DP-14-04 | Central única na web (Início, Reuniões, Assistente, Participantes, Configurações, Diagnóstico) ou só restilizar o assistente atual | Central: é o que transforma o produto em plataforma | Central |
| DP-14-05 | Migrar os diálogos Tk (retranscrever, renomear, corrigir nome) e o diagnóstico .txt para a Central, removendo os Tk | Migrar e remover; dois caminhos geram inconsistência | Migrar |
| DP-14-06 | Abrir a Central em janela de app (`--app=` do Edge/Chrome, sem barra de endereço) quando disponível, com aba como fallback | Sim; dá identidade de aplicativo sem empacotar nada | Sim |
| DP-14-07 | Novo ícone/símbolo (quadrado arredondado, microfone + onda, estados por forma) substituindo o círculo atual | Sim; inclui favicon e ícones da extensão | Sim |
| DP-14-08 | Reduzir o menu da bandeja a ≤ 9 itens de topo movendo configurações raras para a Central | Sim; manter todas as funções acessíveis | Sim |
| DP-14-09 | Adicionar `axe-core`/`@axe-core/playwright` como devDependency para o gate de acessibilidade | Sim; instalado via `npm ci` com lock, sem rede em runtime | Sim |
| DP-14-10 | Nome do produto: manter "Transkriptor" apesar da coincidência com serviço comercial de mesmo nome | Fora do escopo técnico; sinalizado para decisão de marca | Manter |
| DP-14-11 | Versão: a v1.9 vira `config.VERSAO = 1.8.0`, `1.9.0` ou só entra na release seguinte | Decidir em G1; nenhum bump durante A–F | Sem bump |
| DP-14-12 | Ordem: executar a v1.9 só depois de fechar a remediação v1.8 (Task 12 e gates físicos) ou intercalar F14.A após a Task 12 automatizada | Depois da remediação estar commitada; gates físicos podem ficar pendentes em paralelo | **Revisada pelo usuário em 24/09/2026:** iniciar F14.A (T-14.A1) imediatamente, em branch própria `sdd-v1.9-design` criada a partir de `4128cd6`, sem tocar a branch da remediação |

## Decisões herdadas e não reabertas

DU-01 a DU-16 da v1.8 continuam válidas. Em particular: processamento local (DU-02), JSON canônico com TXT como exportação (DU-05), correção manual sem biometria implícita (DU-07), instalação nova protegida (DU-09), testes sintéticos com gate real só sob autorização (DU-12), commit local por task após autorização (DU-13), falha parcial nunca vira sucesso (DU-15).

## Autorizações

- Autorizado em 24/09/2026: commitar os documentos da v1.9 e executar o plano a partir de T-14.A1, uma task por vez, com código, testes, capturas sintéticas e commit local por task, na branch `sdd-v1.9-design`.
- Continua não autorizado: push, tag, release, bump de `config.VERSAO`, instalar dependência além de `@axe-core/playwright` (DP-14-09), gates com reunião real, alterar a branch `remediacao-auditoria-v18` ou qualquer ação externa.

## Condição para nova consulta

Consultar o usuário apenas se: uma decisão DP-14-* precisar mudar depois de iniciada; uma task exigir dependência nova não listada (DP-14-09); a migração de um teste legado for impossível sem perder cobertura comportamental; ou surgir conflito com trabalho local não commitado.
