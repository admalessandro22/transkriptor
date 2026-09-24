// App shell da Central (SDD v1.9, T-14.B1): navegação, tema e barra de estado.
import { ligarTema } from './tema.js';
import { iniciarEstado } from './estado.js';

function marcarPaginaAtiva() {
  const caminho = location.pathname.replace(/\/+$/, '') || '/';
  document.querySelectorAll('.tk-nav__item[data-page]').forEach((a) => {
    const alvo = (a.getAttribute('href') || '').replace(/\/+$/, '') || '/';
    if (alvo === caminho) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
}

function ligarNavegacao() {
  const nav = document.getElementById('nav');
  const toggle = document.getElementById('nav-toggle');
  const fechar = document.getElementById('nav-fechar');
  const scrim = document.getElementById('nav-scrim');
  if (!nav || !toggle) return;
  const abrir = (aberto) => {
    nav.classList.toggle('is-open', aberto);
    if (scrim) scrim.classList.toggle('is-open', aberto);
    toggle.setAttribute('aria-expanded', aberto ? 'true' : 'false');
    if (aberto) { const primeiro = nav.querySelector('.tk-nav__item'); if (primeiro) primeiro.focus(); }
    else toggle.focus();
  };
  toggle.addEventListener('click', () => abrir(!nav.classList.contains('is-open')));
  if (fechar) fechar.addEventListener('click', () => abrir(false));
  if (scrim) scrim.addEventListener('click', () => abrir(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && nav.classList.contains('is-open')) abrir(false); });
}

marcarPaginaAtiva();
ligarNavegacao();
ligarTema();
iniciarEstado();
