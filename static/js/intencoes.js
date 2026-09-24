// Ações rápidas do assistente como intenções (SDD v1.9, T-14.B3).
// O rótulo aparece no chip; o prompt fica aqui e só vai ao campo se o usuário pedir para editar.
export const INTENCOES = [
  { id: 'resumir', rotulo: 'Resumir reunião', icone: 'file-text', primario: true,
    prompt: 'Atue como um analista de reuniões sênior. Elabore um resumo executivo estruturado desta reunião contendo: (1) um parágrafo de contexto sobre o propósito do encontro, (2) os temas centrais discutidos organizados por ordem de relevância, com uma breve descrição de cada um, e (3) uma conclusão com o desfecho geral. Use linguagem objetiva e profissional.' },
  { id: 'pontos', rotulo: 'Pontos principais', icone: 'list',
    prompt: 'Atue como um analista de reuniões sênior. Extraia e liste os pontos principais discutidos nesta reunião. Para cada ponto, apresente: (1) um título curto e descritivo, (2) um resumo do que foi dito sobre o tema e (3) os participantes envolvidos na discussão (se identificáveis). Organize por ordem de importância e impacto. Formate em lista numerada.' },
  { id: 'tarefas', rotulo: 'Tarefas e ações', icone: 'check',
    prompt: "Atue como um project manager. Identifique todas as tarefas, ações e responsabilidades mencionadas nesta reunião. Para cada item, apresente uma tabela com: (1) a tarefa/ação a ser realizada, (2) o responsável atribuído (se mencionado), (3) o prazo ou data limite (se definido), (4) o nível de prioridade (Alta/Média/Baixa) inferido pelo contexto e (5) eventuais dependências de outras tarefas. Se uma informação não foi explicitada, marque como 'a definir'. Destaque as tarefas críticas em primeiro lugar." },
  { id: 'decisoes', rotulo: 'Decisões', icone: 'shield',
    prompt: "Atue como um analista de negócios. Identifique e liste todas as decisões tomadas durante esta reunião. Para cada decisão, apresente: (1) a decisão em si de forma clara, (2) o contexto ou problema que motivou a decisão, (3) quem propôs ou defendeu a decisão (se identificável) e (4) o impacto esperado dessa decisão. Caso existam decisões que foram apenas parcialmente acordadas ou que ainda dependam de validação posterior, destaque-as separadamente como 'decisões pendentes de confirmação'." },
  { id: 'proximos', rotulo: 'Próximos passos', icone: 'chevron-right',
    prompt: 'Atue como um project manager. Extraia e organize os próximos passos definidos nesta reunião em um plano de ação claro e acionável. Para cada item, inclua: (1) a ação concreta a ser executada, (2) o responsável (se mencionado), (3) o prazo (se definido), (4) o critério de conclusão esperado e (5) a prioridade (Alta/Média/Baixa). Agrupe as ações por prazo (curto prazo / médio prazo / longo prazo). Inclua também qualquer reunião de acompanhamento mencionada.' },
  { id: 'pendencias', rotulo: 'Pendências e riscos', icone: 'alert',
    prompt: 'Atue como um consultor de riscos. Identifique todos os itens que ficaram em aberto, pendentes ou sem resolução nesta reunião. Classifique cada item como: Dúvida (pergunta sem resposta), Risco (potencial problema identificado) ou Pendência (ação que depende de algo externo). Para cada um, apresente: (1) a descrição do item, (2) o tipo de classificação, (3) o nível de criticidade (Alto/Médio/Baixo), (4) quem precisa responder ou resolver (se aplicável) e (5) uma sugestão de mitigação ou próximo passo para encerrar o item.' },
];

export function intencaoPorId(id) {
  return INTENCOES.find((i) => i.id === id) || null;
}
