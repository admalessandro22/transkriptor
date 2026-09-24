// Alternância de tema da Central (SDD v1.9, T-14.B1); a persistência mora em ui.js.
import { alternarTema, aplicarTema } from './ui.js';

export function ligarTema(botao = document.getElementById('tema-toggle')) {
  aplicarTema();
  if (!botao) return;
  botao.addEventListener('click', () => alternarTema());
  const media = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)');
  if (media && media.addEventListener) media.addEventListener('change', () => aplicarTema());
}
