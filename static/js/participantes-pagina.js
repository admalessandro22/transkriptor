// Página Participantes (SDD v1.9, T-14.C1): mesmo módulo do painel, aberto de saída.
import { iniciarParticipantes, carregarReunioes } from './participantes.js';

iniciarParticipantes({ modo: 'pagina' });
carregarReunioes();
