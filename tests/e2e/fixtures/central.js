// Dados sintéticos e estáveis para E2E e capturas (SDD v1.9). Nenhum nome real.
"use strict";

function reunioes(n = 3) {
  const base = [
    { arquivo: "2026-09-22_10h03_diarizado.txt", data: "22/09/2026 10:03", tipo: "diarizado", tamanho_kb: 96.4, com_sua_voz: true },
    { arquivo: "2026-09-18_15h30.txt", data: "18/09/2026 15:30", tipo: "transcricao", tamanho_kb: 41.2, com_sua_voz: false },
    { arquivo: "2026-09-11_09h00_diarizado.tkpt", data: "11/09/2026 09:00", tipo: "diarizado", tamanho_kb: 12.8, com_sua_voz: false }
  ];
  const lista = [];
  for (let i = 0; i < n; i++) {
    const item = Object.assign({}, base[i % base.length]);
    if (i >= base.length) item.arquivo = `2026-08-${String(30 - (i % 28)).padStart(2, "0")}_${String(8 + (i % 10)).padStart(2, "0")}h00_${i}.txt`;
    lista.push(item);
  }
  return lista;
}

function indice(n = 3, cursor = null) {
  return {
    reunioes: reunioes(n).map((r, i) => ({
      meeting_id: r.arquivo.replace(/\.(txt|tkpt)$/, ""),
      title: null,
      started_at: `2026-09-${String(22 - i).padStart(2, "0")}T10:03:00`,
      duration_ms: 1800000 + i * 60000,
      revision: "rev-" + (i + 1),
      quality_state: i === 0 ? "complete" : "partial"
    })),
    proximo: cursor
  };
}

function modelos() {
  return ["llama3.1:8b", "qwen2.5:7b"];
}

function resultado() {
  return {
    schema_version: 1,
    revision: "rev-3",
    segmentos: [
      { segment_id: "s1", start_ms: 0, end_ms: 4000, audio_source: "loopback", text: "Bom dia a todos, vamos começar pela pauta do dia.", speaker_cluster_id: "FALANTE_00", overlap: false,
        assignment: { status: "suggested", participant_id: "p1", display_name: "Ana Souza", source: "caption", confidence: 0.91 } },
      { segment_id: "s2", start_ms: 4000, end_ms: 9000, audio_source: "microfone", text: "Perfeito. Eu fico com a parte de integração.", speaker_cluster_id: "FALANTE_01", overlap: false },
      { segment_id: "s3", start_ms: 9000, end_ms: 14000, audio_source: "loopback", text: "Então fechamos o prazo para sexta.", speaker_cluster_id: "FALANTE_00", overlap: false,
        assignment: { status: "suggested", participant_id: "p1", display_name: "Ana Souza", source: "caption", confidence: 0.88 } },
      { segment_id: "s4", start_ms: 14000, end_ms: 17000, audio_source: "loopback", text: "Eu reviso o documento até quinta.", speaker_cluster_id: "FALANTE_02", overlap: false }
    ],
    mapeamento: { FALANTE_01: { display_name: "VOCÊ", origem: "voz" } },
    historico: []
  };
}

function estado(nome = "aguardando") {
  const rotulos = {
    aguardando: "Aguardando reunião", gravando: "Gravando", processando: "Processando reunião",
    separando_vozes: "Separando vozes", pausado: "Pausado", erro: "Erro"
  };
  return {
    estado: nome, rotulo: rotulos[nome] || nome, fontes: nome === "gravando" ? ["titulo", "microfone"] : [],
    processamento: nome === "processando" ? "Processando" : null, protecao: "protected",
    ultima_reuniao: { meeting_id: "2026-09-22_10h03_diarizado", started_at: "2026-09-22T10:03:00", estado: "Pronta" },
    versao: "1.7.0", gerado_em: "2026-09-24T12:00:00Z"
  };
}

function config() {
  return {
    deteccao_ativa: true, diarizacao_ativa: true, identificar_minha_voz: false, usar_nomes_meet: false,
    modo_legendas_meet: false, criptografar_transcricoes: true, protection_mode: "protected",
    modelo_whisper: "auto", iniciar_com_windows: false, perfil_voz_existe: false
  };
}

function diagnostico() {
  return {
    itens: [
      { nome: "numpy", estado: "OK", detalhe: "2.1.0" },
      { nome: "soundcard", estado: "OK", detalhe: "0.4.6" },
      { nome: "Áudio do sistema (loopback)", estado: "AVISO", detalhe: "captura funciona, mas está em silêncio agora" },
      { nome: "Microfone", estado: "ERRO", detalhe: "nenhum dispositivo de entrada encontrado" }
    ],
    erros: 1, avisos: 1, relatorio: "diagnostico_2026-09-24_12h00.txt"
  };
}

function resposta() {
  return "## Resumo executivo\n\nA reunião tratou do **planejamento do sprint**.\n\n| Tarefa | Responsável | Prazo |\n|---|---|---|\n| Integração | VOCÊ | sexta |\n| Revisão do documento | Falante 3 | quinta |\n\n1. Integração fica com VOCÊ\n2. Prazo: sexta-feira\n\n- Risco: dependência externa";
}

module.exports = { reunioes, indice, modelos, resultado, estado, config, diagnostico, resposta };
