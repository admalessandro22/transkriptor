/**
 * Transkriptor Meet Bridge — legendas e nomes sem a faixa de legendas (CC).
 *
 * Roda no mundo da página (manifest: "world": "MAIN", document_start) para
 * enxergar o RTCPeerConnection do Meet, como fazem as extensões de transcrição:
 *
 *   1. canal remoto "collections" (e a resposta de SyncMeetingSpaceCollections)
 *      trazem deviceId -> nome de cada participante;
 *   2. abrimos o NOSSO canal "captions_v2" na conexão do Meet; o servidor passa
 *      a mandar as legendas por ele, mesmo com o CC desligado na tela;
 *   3. cada legenda (deviceId, utterance, versão, texto) sobe ao content script.
 *
 * Nada aparece na reunião e nada sai do navegador por aqui: o content script
 * recebe um CustomEvent com JSON e só o background.js fala com o app local.
 * Não alteramos o protocolo do Meet (idioma, media-session): só lemos.
 */
(function () {
  "use strict";

  const EVENTO = "transkriptor-meet-rtc";
  const CANAL_LEGENDAS = "captions_v2";
  const URL_COLECOES =
    "https://meet.google.com/$rpc/google.rtc.meetings.v1.MeetingSpaceService/SyncMeetingSpaceCollections";
  const URL_ATUALIZAR_MIDIA =
    "https://meet.google.com/$rpc/google.rtc.meetings.v1.MediaSessionService/UpdateMediaSession";
  const URL_CRIAR_DISPOSITIVO =
    "https://meet.google.com/$rpc/google.rtc.meetings.v1.MeetingDeviceService/CreateMeetingDevice";
  // FR-15.B2: o Meet põe o próprio dispositivo em texto legível nessas chamadas.
  const PADRAO_DISPOSITIVO = /spaces\/[A-Za-z0-9_-]+\/devices\/([A-Za-z0-9_-]+)/;
  // BCP-47 com região, como o Meet usa nas legendas ("pt-BR", "en-US").
  const PADRAO_IDIOMA = /^[a-z]{2,3}-[A-Z]{2}$/;
  const MAX_TEXTO = 500;
  const MAX_NOME = 80;
  const MAX_REABERTURAS = 5;

  // ---------- protobuf mínimo (só leitura + o ack de legenda) ----------

  /** Campos de uma mensagem protobuf: {numero: [valor, ...]}; bytes ficam Uint8Array. */
  function lerProto(buf) {
    const campos = {};
    let i = 0;
    function varint() {
      let x = 0;
      let escala = 1;
      let b;
      do {
        if (i >= buf.length) throw new Error("varint truncado");
        b = buf[i++];
        x += (b & 127) * escala;
        escala *= 128;
      } while (b & 128);
      return x;
    }
    while (i < buf.length) {
      const chave = varint();
      const numero = Math.floor(chave / 8);
      const tipo = chave & 7;
      let valor;
      if (tipo === 0) valor = varint();
      else if (tipo === 2) {
        const n = varint();
        if (i + n > buf.length) throw new Error("campo truncado");
        valor = buf.subarray(i, i + n);
        i += n;
      } else if (tipo === 1) {
        i += 8;
        continue;
      } else if (tipo === 5) {
        i += 4;
        continue;
      } else throw new Error("wire type " + tipo);
      (campos[numero] = campos[numero] || []).push(valor);
    }
    return campos;
  }

  function primeiro(campos, numero) {
    return campos && campos[numero] ? campos[numero][0] : undefined;
  }

  function sub(campos, numero) {
    const v = primeiro(campos, numero);
    return v instanceof Uint8Array ? lerProto(v) : null;
  }

  const decodificador = new TextDecoder();
  function texto(v) {
    return v instanceof Uint8Array ? decodificador.decode(v) : "";
  }

  function escreverVarint(saida, x) {
    while (x >= 128) {
      saida.push((x % 128) | 128);
      x = Math.floor(x / 128);
    }
    saida.push(x);
  }

  function campoMensagem(numero, conteudo) {
    const saida = [];
    escreverVarint(saida, numero * 8 + 2);
    escreverVarint(saida, conteudo.length);
    return saida.concat(conteudo);
  }

  function campoVarint(numero, valor) {
    const saida = [];
    escreverVarint(saida, numero * 8);
    escreverVarint(saida, valor);
    return saida;
  }

  /** Confirmação de recebimento: sem ela o servidor reenvia a mesma legenda. */
  function ackLegenda(utterance, versao) {
    const ref = campoVarint(1, utterance).concat(campoVarint(2, versao), campoVarint(3, 1));
    return new Uint8Array(campoMensagem(1, campoMensagem(1, ref)));
  }

  // ---------- gzip: o Meet compacta parte das mensagens ----------

  function inicioGzip(u) {
    for (let j = 0; j < 6 && j + 2 < u.length; j++) {
      if (u[j] === 31 && u[j + 1] === 139 && u[j + 2] === 8) return j;
    }
    return -1;
  }

  async function descompactar(dados) {
    const u = dados instanceof Uint8Array ? dados : new Uint8Array(dados);
    const k = inicioGzip(u);
    if (k < 0) return u;
    const fluxo = new Response(u.subarray(k)).body.pipeThrough(new DecompressionStream("gzip"));
    return new Uint8Array(await new Response(fluxo).arrayBuffer());
  }

  async function bytesDe(dados) {
    if (dados instanceof Blob) return descompactar(await dados.arrayBuffer());
    if (typeof dados === "string") return null;
    return descompactar(dados);
  }

  // ---------- decodificação das mensagens do Meet ----------

  /** "spaces/<sala>/devices/127" -> "dev-127": o id da sala nunca sai daqui. */
  function idDispositivo(bruto) {
    const m = /devices\/([A-Za-z0-9_-]+)$/.exec(bruto || "");
    return m ? "dev-" + m[1] : null;
  }

  function limparNome(nome) {
    const n = (nome || "").replace(/\s+/g, " ").trim();
    return n && n.length < MAX_NOME ? n : "";
  }

  // ---------- idioma (FR-15.B1, só leitura) ----------

  /** ArrayBuffer de qualquer realm (instanceof falha entre janelas/ambientes). */
  function ehArrayBuffer(valor) {
    return Object.prototype.toString.call(valor) === "[object ArrayBuffer]";
  }

  /** Códigos de idioma em folhas de texto, sem olhar os campos em `ignorar`. */
  function idiomasEm(campos, profundidade, ignorar) {
    const achados = [];
    Object.keys(campos).forEach(function (numero) {
      if (ignorar && ignorar.has(Number(numero))) return;
      campos[numero].forEach(function (valor) {
        if (!(valor instanceof Uint8Array) || !valor.length) return;
        const s = valor.length <= 16 ? texto(valor) : "";
        if (PADRAO_IDIOMA.test(s)) {
          achados.push(s);
          return;
        }
        if (profundidade > 0) {
          try {
            achados.push(...idiomasEm(lerProto(valor), profundidade - 1, null));
          } catch (_e) {}
        }
      });
    });
    return achados;
  }

  /** Idioma pedido pelo próprio Meet no corpo do UpdateMediaSession (binário ou base64). */
  function idiomaDoCorpo(corpo) {
    let bytes = null;
    if (ArrayBuffer.isView(corpo)) bytes = new Uint8Array(corpo.buffer, corpo.byteOffset, corpo.byteLength);
    else if (ehArrayBuffer(corpo)) bytes = new Uint8Array(corpo);
    else if (typeof corpo === "string") {
      try {
        const s = /^[A-Za-z0-9+/=\s]+$/.test(corpo) ? atob(corpo.trim()) : corpo;
        bytes = Uint8Array.from(s, (ch) => ch.charCodeAt(0) & 255);
      } catch (_e) {
        return null;
      }
    }
    if (!bytes) return null;
    try {
      return idiomasEm(lerProto(bytes), 6, null)[0] || null;
    } catch (_e) {
      return null;
    }
  }

  // ---------- dispositivo próprio (FR-15.B2) ----------

  /** "spaces/<sala>/devices/88" em texto, bytes ou base64 -> "dev-88"; a sala não sai. */
  function dispositivoProprioEm(corpo) {
    let s = null;
    if (typeof corpo === "string") s = corpo;
    else if (ArrayBuffer.isView(corpo)) s = new TextDecoder().decode(new Uint8Array(corpo.buffer, corpo.byteOffset, corpo.byteLength));
    else if (ehArrayBuffer(corpo)) s = new TextDecoder().decode(new Uint8Array(corpo));
    if (s === null) return null;
    let m = PADRAO_DISPOSITIVO.exec(s);
    if (!m && /^[A-Za-z0-9+/=\s]+$/.test(s)) {
      try {
        m = PADRAO_DISPOSITIVO.exec(atob(s.trim()));
      } catch (_e) {}
    }
    return m ? "dev-" + m[1] : null;
  }

  let proprioPublicado = false;
  function publicarProprio(dispositivo) {
    if (!dispositivo || proprioPublicado) return;
    proprioPublicado = true;
    publicar({ tipo: "proprio", dispositivo });
  }

  /** CaptionsV2Packet: 1{1 utterance, 2 versão, 3{3 texto, 6 deviceId}}. */
  function decodificarLegenda(u) {
    const pacote = lerProto(u);
    const fala = sub(pacote, 1);
    if (!fala) return null;
    const legenda = sub(fala, 3);
    const utterance = primeiro(fala, 1);
    if (!legenda || typeof utterance !== "number" || !utterance) return null;
    const dispositivo = idDispositivo(texto(primeiro(legenda, 6)));
    if (!dispositivo) return null;
    const versao = primeiro(fala, 2);
    return {
      dispositivo,
      utterance,
      versao: typeof versao === "number" ? versao : 0,
      texto: texto(primeiro(legenda, 3)).slice(0, MAX_TEXTO),
      // Texto (3) e dispositivo (6) nunca contam como idioma.
      idioma: idiomasEm(legenda, 3, new Set([3, 6]))[0] || null,
    };
  }

  /** {1 deviceId, 2 nome} -> par válido ou null. */
  function parDispositivo(campos) {
    const dispositivo = idDispositivo(texto(primeiro(campos, 1)));
    const nome = limparNome(texto(primeiro(campos, 2)));
    return dispositivo && nome ? { dispositivo, nome } : null;
  }

  /** Canal "collections": 1{2{13{1{2{1 id, 2 nome}}}}}. */
  function decodificarDispositivo(u) {
    let c = lerProto(u);
    for (const numero of [1, 2, 13, 1, 2]) {
      c = sub(c, numero);
      if (!c) return [];
    }
    const par = parDispositivo(c);
    return par ? [par] : [];
  }

  /** Resposta de SyncMeetingSpaceCollections: 2{2{2[] {1 id, 2 nome}}}. */
  function decodificarColecao(u) {
    let c = lerProto(u);
    for (const numero of [2, 2]) {
      c = sub(c, numero);
      if (!c) return [];
    }
    return (c[2] || [])
      .filter((v) => v instanceof Uint8Array)
      .map((v) => parDispositivo(lerProto(v)))
      .filter(Boolean);
  }

  // ---------- horário da fala (FR-15.A1) ----------

  const MAX_TEMPOS = 512;

  /** Época em ms no relógio monotônico da página, com resolução sub-ms. */
  function agoraPagina() {
    return performance.timeOrigin + performance.now();
  }

  /** "utterance/dispositivo" -> início da fala; ordem de inserção = recência. */
  function novoRegistroTempos() {
    return new Map();
  }

  /** O primeiro pacote de cada fala define o início; revisões só avançam o fim. */
  function carimbarLegenda(registro, legenda, agoraMs) {
    const id = legenda.utterance + "/" + legenda.dispositivo;
    let inicio = registro.get(id);
    if (inicio === undefined) {
      inicio = agoraMs;
      if (registro.size >= MAX_TEMPOS) registro.delete(registro.keys().next().value);
    } else {
      registro.delete(id);
    }
    registro.set(id, inicio);
    return Object.assign({}, legenda, { t_inicio_ms: inicio, t_ultimo_ms: agoraMs });
  }

  /** Decodifica, confirma e publica um pacote do canal com o horário da chegada. */
  async function tratarPacoteLegenda(dados, deps) {
    const chegada = deps.agora();
    const u = await bytesDe(dados);
    const legenda = u && decodificarLegenda(u);
    if (!legenda) return;
    try {
      deps.enviarAck(ackLegenda(legenda.utterance, legenda.versao));
    } catch (_e) {}
    const carimbada = carimbarLegenda(deps.registro, legenda, chegada);
    deps.publicar(Object.assign({ tipo: "legenda", canal: CANAL_LEGENDAS }, carimbada));
  }

  // ---------- ponte com o content script ----------

  function publicar(mensagem) {
    try {
      document.dispatchEvent(new CustomEvent(EVENTO, { detail: JSON.stringify(mensagem) }));
    } catch (_e) {}
  }

  function publicarNomes(pares) {
    if (pares && pares.length) publicar({ tipo: "nomes", pares });
  }

  // ---------- captura ----------

  const temposFalas = novoRegistroTempos();
  const nossos = new WeakSet();
  const conexoesComLegenda = new WeakSet();
  let proximoId = 61000;

  function abrirCanalLegendas(pc, tentativa) {
    if (pc.connectionState === "closed" || pc.connectionState === "failed") return;
    let canal;
    try {
      canal = pc.createDataChannel(CANAL_LEGENDAS, { ordered: true, maxRetransmits: 10, id: ++proximoId });
    } catch (_e) {
      return;
    }
    nossos.add(canal);
    canal.binaryType = "arraybuffer";
    canal.addEventListener("message", function (ev) {
      tratarPacoteLegenda(ev.data, {
        registro: temposFalas,
        agora: agoraPagina,
        enviarAck: (bytes) => canal.send(bytes),
        publicar,
      }).catch(() => {});
    });
    canal.addEventListener("close", function () {
      if (tentativa >= MAX_REABERTURAS) return;
      if (pc.connectionState === "closed" || pc.connectionState === "failed") return;
      setTimeout(function () {
        abrirCanalLegendas(pc, tentativa + 1);
      }, 1000);
    });
  }

  function ouvirColecoes(canal) {
    canal.addEventListener("message", async function (ev) {
      try {
        const u = await bytesDe(ev.data);
        if (u) publicarNomes(decodificarDispositivo(u));
      } catch (_e) {}
    });
  }

  function instalarRtc() {
    const Original = window.RTCPeerConnection;
    if (typeof Original !== "function" || Original.__transkriptor) return;
    function Envolvida(...args) {
      const pc = new Original(...args);
      pc.addEventListener("datachannel", function (ev) {
        const canal = ev.channel;
        if (!canal || canal.label !== "collections") return;
        ouvirColecoes(canal);
        // "collections" só existe na conexão principal da chamada: é nela
        // que o servidor aceita o canal de legendas.
        if (!conexoesComLegenda.has(pc)) {
          conexoesComLegenda.add(pc);
          abrirCanalLegendas(pc, 0);
        }
      });
      return pc;
    }
    Envolvida.prototype = Original.prototype;
    Object.setPrototypeOf(Envolvida, Original);
    Envolvida.__transkriptor = true;
    window.RTCPeerConnection = Envolvida;
  }

  function instalarFetch() {
    const original = window.fetch;
    if (typeof original !== "function") return;
    window.fetch = function (recurso) {
      const promessa = original.apply(this, arguments);
      try {
        const url = typeof recurso === "string" ? recurso : recurso && recurso.url;
        if (url === URL_ATUALIZAR_MIDIA) {
          const codigo = idiomaDoCorpo(arguments[1] && arguments[1].body);
          if (codigo) publicar({ tipo: "idioma", codigo, origem: "meet", resultado: "lido" });
        }
        if (url === URL_COLECOES) publicarProprio(dispositivoProprioEm(arguments[1] && arguments[1].body));
        if (url === URL_CRIAR_DISPOSITIVO) {
          promessa
            .then((resposta) => resposta.clone().text())
            .then((corpo) => publicarProprio(dispositivoProprioEm(corpo)))
            .catch(() => {});
        }
        if (url === URL_COLECOES) {
          promessa
            .then((resposta) => resposta.clone().text())
            .then((corpo) => {
              const bytes = Uint8Array.from(atob(corpo.trim()), (ch) => ch.charCodeAt(0));
              publicarNomes(decodificarColecao(bytes));
            })
            .catch(() => {});
        }
      } catch (_e) {}
      return promessa;
    };
  }

  const API = {
    lerProto,
    decodificarLegenda,
    decodificarDispositivo,
    decodificarColecao,
    idiomaDoCorpo,
    dispositivoProprioEm,
    ackLegenda,
    idDispositivo,
    descompactar,
    agoraPagina,
    novoRegistroTempos,
    carimbarLegenda,
    tratarPacoteLegenda,
    MAX_TEMPOS,
    EVENTO,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = API;
    return;
  }
  instalarRtc();
  instalarFetch();
})();
