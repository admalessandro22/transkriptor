// Interações da galeria (SDD v1.9, T-14.A3): usa as primitivas de ui.js.
import { toast, confirmar, abrirPainel, fecharPainel, alternarTema } from './ui.js';

document.querySelectorAll('[data-toast]').forEach((b) => {
  b.addEventListener('click', () => {
    const tipo = b.dataset.toast;
    const textos = {
      info: ['Prompt carregado', 'Edite se quiser e pressione Enviar.'],
      success: ['Correção salva', 'Revisão 4.'],
      warning: ['Transcrição longa', 'A resposta será consolidada em blocos.'],
      error: ['Ollama não respondeu', 'Inicie o Ollama e tente de novo.'],
    };
    toast(tipo, textos[tipo][0], textos[tipo][1]);
  });
});

const resultado = document.getElementById('dialogo-resultado');
document.getElementById('abrir-dialogo').addEventListener('click', async () => {
  const ok = await confirmar({ titulo: 'Pausar a gravação automática?', consequencia: 'Enquanto pausado, o Transkriptor não grava nenhuma reunião.', confirmarRotulo: 'Pausar' });
  resultado.textContent = ok ? 'Confirmado' : 'Cancelado';
});
document.getElementById('abrir-dialogo-perigo').addEventListener('click', async () => {
  const ok = await confirmar({ titulo: 'Apagar o perfil de voz?', consequencia: 'A identificação VOCÊ deixa de funcionar até um novo cadastro. Não pode ser desfeito.', confirmarRotulo: 'Apagar', perigo: true });
  resultado.textContent = ok ? 'Confirmado' : 'Cancelado';
});

document.getElementById('abrir-painel').addEventListener('click', () => abrirPainel('painel-demo'));
document.getElementById('fechar-painel').addEventListener('click', () => fecharPainel('painel-demo'));
document.getElementById('painel-cancelar').addEventListener('click', () => fecharPainel('painel-demo'));
document.getElementById('tema-toggle').addEventListener('click', () => alternarTema());
