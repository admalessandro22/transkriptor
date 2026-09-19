#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate de verificação por fase — Transkriptor SDD."""
import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

FASES = {
    0: ["tests/test_detector_meet.py", "tests/test_fixtures.py"],
    1: ["tests/test_assistente_seguranca.py", "tests/test_assistente_startup.py"],
    2: ["tests/test_config_device.py", "tests/test_mutex.py", "tests/test_transkiptor_estado.py"],
    3: ["tests/test_crypto_storage.py", "tests/test_transcricao_crypto.py"],
    4: [
        "tests/test_notificador.py",
        "tests/test_diarizador_progresso.py",
        "tests/test_assistente_api.py",
    ],
    5: ["tests/test_token_sessao.py", "tests/test_detector_meet_visivel.py"],
    6: ["tests/test_gitignore_docs.py"],
    7: [
        "tests/test_identificador_voz.py",
        "tests/test_captura_mic.py",
        "tests/test_diarizacao_voce.py",
        "tests/test_assistente_badge_voce.py",
    ],
    8: [
        "tests/test_meet_bridge.py",
        "tests/test_correlacionador.py",
        "tests/test_renomear_falante_flow.py",
        "tests/test_config_portas.py",
    ],
    "estabilidade": [
        "tests/test_bandeja_lifecycle.py",
        "tests/test_detector_meet.py",
        "tests/test_integracao_monitor_meet.py",
        "tests/test_atalho_desktop.py",
    ],
    "v1.5-estatico": [
        "tests/test_versao.py",
        "tests/test_manual_usuario.py",
        "tests/test_limite_linhas.py",
        "tests/test_fluxo_reuniao_v15.py",
    ],
    "v1.6-estatico": [
        "tests/test_v16_a_tokens.py",
        "tests/test_v16_b_assistente.py",
        "tests/test_v16_c_a11y.py",
        "tests/test_v16_d_bandeja.py",
        "tests/test_v16_e_dialogs.py",
        "tests/test_v16_f_consentimento.py",
        "tests/test_v16_g_qualidade.py",
        "tests/test_limite_linhas.py",
        "tests/test_versao.py",
    ],
}

ARQUIVOS_SDD_V18 = (
    "README.md",
    "plan.md",
    "concept.md",
    "spec.md",
    "tasks.md",
    "decisoes-usuario.md",
    "interfaces.md",
    "executor-llm.md",
)
LINKS_INDICE_V18 = (
    "plan.md",
    "concept.md",
    "spec.md",
    "tasks.md",
    "decisoes-usuario.md",
    "interfaces.md",
    "executor-llm.md",
)
PADRAO_REQUISITO_TASK = re.compile(
    r"^\|\s*([A-Z]+-\d+\.[A-Z]\d+)\s*\|.*?\|\s*"
    r"(T-\d+\.[A-Z]\d+)\s*\|\s*$",
    re.MULTILINE,
)
PADRAO_TASK = re.compile(r"^###\s+(T-\d+\.[A-Z]\d+)\b", re.MULTILINE)
PADRAO_SELETOR_PYTEST = re.compile(r"\b(tests/[A-Za-z0-9_./-]+\.py)\b")


def bloco_da_tarefa(tasks_text: str, tarefa: str) -> str | None:
    """Obtém o bloco Markdown de uma única tarefa pelo ID normativo."""
    inicio = re.search(rf"^###\s+{re.escape(tarefa)}\b", tasks_text, re.MULTILINE)
    if inicio is None:
        return None
    proximo = PADRAO_TASK.search(tasks_text, inicio.end())
    return tasks_text[inicio.end(): proximo.start() if proximo else len(tasks_text)]


def auditar_sdd_v18(sdd_root: Path, tarefa: str | None = None) -> list[str]:
    """Retorna inconsistências do mapa normativo requisito → tarefa.

    A auditoria analisa a documentação, não presume que os testes de tarefas
    futuras já existam. Cada tarefa, contudo, precisa declarar seu seletor de
    teste final; a existência física é verificada quando a própria tarefa é
    executada no respectivo gate.
    """
    erros: list[str] = []
    root = sdd_root.resolve()
    faltantes = [nome for nome in ARQUIVOS_SDD_V18 if not (root / nome).is_file()]
    if faltantes:
        return [f"arquivos SDD ausentes: {', '.join(faltantes)}"]

    indice = (root / "README.md").read_text(encoding="utf-8")
    for link in LINKS_INDICE_V18:
        if f"]({link})" not in indice:
            erros.append(f"índice sem link obrigatório: {link}")

    spec = (root / "spec.md").read_text(encoding="utf-8")
    tasks_text = (root / "tasks.md").read_text(encoding="utf-8")
    tarefas = set(PADRAO_TASK.findall(tasks_text))
    mapeamentos = PADRAO_REQUISITO_TASK.findall(spec)

    if not mapeamentos:
        erros.append("spec sem mapeamento requisito → task")
    for requisito, task_id in mapeamentos:
        if task_id not in tarefas:
            erros.append(f"requisito sem task: {requisito} -> {task_id}")

    tarefas_mapeadas = {task_id for _, task_id in mapeamentos}
    for task_id in sorted(tarefas):
        if task_id not in tarefas_mapeadas:
            erros.append(f"task sem requisito: {task_id}")

    for match in PADRAO_TASK.finditer(tasks_text):
        proximo = PADRAO_TASK.search(tasks_text, match.end())
        bloco = tasks_text[match.end(): proximo.start() if proximo else len(tasks_text)]
        if "**Teste final:**" not in bloco:
            erros.append(f"task sem seletor de teste final: {match.group(1)}")

    if tarefa is not None:
        bloco = bloco_da_tarefa(tasks_text, tarefa)
        if bloco is None:
            erros.append(f"tarefa não encontrada: {tarefa}")
        elif "**Teste final:**" not in bloco:
            erros.append(f"task sem seletor de teste final: {tarefa}")
        else:
            teste_final = bloco.split("**Teste final:**", 1)[1].split("**Aceite", 1)[0]
            seletores = PADRAO_SELETOR_PYTEST.findall(teste_final)
            if not seletores:
                erros.append(f"task sem seletor pytest: {tarefa}")
            for seletor in seletores:
                if not (REPO / seletor).is_file():
                    erros.append(f"seletor ausente para {tarefa}: {seletor}")

    return erros


def verificar_sdd_v18(sdd_root: Path, tarefa: str | None = None) -> int:
    erros = auditar_sdd_v18(sdd_root, tarefa)
    if erros:
        print("RASTREABILIDADE FALHOU", file=sys.stderr)
        for erro in erros:
            print(f"- {erro}", file=sys.stderr)
        return 1
    sufixo = f"; tarefa={tarefa}" if tarefa is not None else ""
    print(f"RASTREABILIDADE OK: {sdd_root.resolve()}{sufixo}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Verifica gate de fase SDD")
    parser.add_argument(
        "--fase",
        required=True,
        help=(
            "Número da fase (0-8), 'estabilidade', 'v1.5-estatico', "
            "'v1.6-estatico', 'v1.8-sdd' ou 'all'"
        ),
    )
    parser.add_argument(
        "--sdd-root",
        type=Path,
        default=REPO / "docs" / "sdd" / "v1.8",
        help="Raiz da documentação v1.8 auditada por --fase v1.8-sdd.",
    )
    parser.add_argument(
        "--tarefa",
        help=(
            "ID da tarefa v1.8 em execução. Além do mapa SDD, valida que os "
            "seletores pytest declarados no teste final existem no repositório."
        ),
    )
    args = parser.parse_args()

    if args.fase == "v1.8-sdd":
        return verificar_sdd_v18(args.sdd_root, args.tarefa)

    if args.fase == "all":
        rastreabilidade = verificar_sdd_v18(args.sdd_root)
        if rastreabilidade:
            return rastreabilidade
        files = sorted({f for fl in FASES.values() for f in fl})
    elif args.fase in FASES:
        files = FASES[args.fase]
    else:
        try:
            fase = int(args.fase)
        except ValueError:
            print(f"Fase inválida: {args.fase}", file=sys.stderr)
            return 1
        files = FASES.get(fase)
        if files is None:
            print(f"Fase {fase} não definida.", file=sys.stderr)
            return 1

    missing = [f for f in files if not (REPO / f).is_file()]
    if missing:
        print(f"TESTES AUSENTES: {missing}", file=sys.stderr)
        return 1

    cmd = [sys.executable, "-m", "pytest", *files, "-v", "--tb=short"]
    print(f"Executando: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
