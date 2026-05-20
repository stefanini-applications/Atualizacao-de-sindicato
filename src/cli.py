"""Interface de linha de comando para o registro de documentos sindicais.

Comandos disponíveis:
  scan            Varre a pasta CCT/ e atualiza o registro
  list            Exibe lista consolidada de documentos
  show-incomplete Exibe documentos com campos de cadastro incompletos
  summary         Exibe resumo estatístico do registro
  extract         Extrai texto bruto dos PDFs cadastrados no registro
  ocr             Executa OCR nos PDFs classificados como sem_texto_extraivel
  check-ocr-env   Verifica se o ambiente possui as dependências necessárias para OCR
"""

import argparse
import sys
from pathlib import Path

from src.services.scanner import varrer_pasta_cct
from src.services.registry import carregar, salvar, upsert
from src.services.extractor import processar_extracao
from src.services.extraction_store import salvar_textos, carregar_textos
from src.reports.consolidated import imprimir_lista, imprimir_resumo
from src.reports.extraction import imprimir_relatorio_extracao
from src.reports.ocr import imprimir_relatorio_ocr
from src.services.validator import campos_criticos_ausentes_ou_invalidos, campos_incompletos
from src.services.env_checker import verificar_ambiente_ocr, imprimir_resultado_verificacao
from src.models.texto_extraido import TextoExtraido

DEFAULT_CCT_DIR = "CCT"
DEFAULT_REGISTRY = "data/registro_documentos.json"
DEFAULT_EXTRACTION_OUTPUT = "data/textos_extraidos.json"
DEFAULT_OCR_OUTPUT = "data/textos_ocr.json"


def _raiz_repo() -> Path:
    """Retorna a raiz do repositório (diretório do script ou CWD)."""
    return Path(__file__).parent.parent


def cmd_scan(args: argparse.Namespace) -> int:
    raiz = _raiz_repo()
    cct_dir = raiz / args.cct_dir
    registry_path = raiz / args.registry

    if not cct_dir.is_dir():
        print(f"Erro: pasta CCT não encontrada em '{cct_dir}'", file=sys.stderr)
        return 1

    print(f"Varrendo '{cct_dir}'...")
    novos = varrer_pasta_cct(cct_dir, raiz, responsavel=args.responsavel)
    print(f"  {len(novos)} arquivo(s) PDF encontrado(s).")

    registro = carregar(registry_path)
    stats = upsert(registro, novos)
    salvar(registry_path, registro)

    print(f"  Inseridos : {stats['inseridos']}")
    print(f"  Atualizados: {stats['atualizados']}")
    print(f"Registro salvo em '{registry_path}'.")

    invalidos = [d for d in registro.values() if campos_criticos_ausentes_ou_invalidos(d)]
    if invalidos:
        print(f"\n⚠  {len(invalidos)} documento(s) com campos críticos ausentes/inválidos"
              " (inválidos para extração).")
        print("   Execute 'list --invalid-only' para ver os detalhes.")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    raiz = _raiz_repo()
    registry_path = raiz / args.registry

    registro = carregar(registry_path)
    if not registro:
        print("Registro vazio. Execute 'scan' primeiro.")
        return 0

    imprimir_lista(
        list(registro.values()),
        apenas_invalidos=args.invalid_only,
        apenas_incompletos=args.incomplete_only,
    )
    return 0


def cmd_show_incomplete(args: argparse.Namespace) -> int:
    raiz = _raiz_repo()
    registry_path = raiz / args.registry

    registro = carregar(registry_path)
    if not registro:
        print("Registro vazio. Execute 'scan' primeiro.")
        return 0

    docs_incompletos = [d for d in registro.values() if campos_incompletos(d)]

    if not docs_incompletos:
        print("Todos os documentos estão com campos de cadastro completos.")
        return 0

    print(f"\n{len(docs_incompletos)} documento(s) com campos de cadastro incompletos:\n")
    for doc in sorted(docs_incompletos, key=lambda d: (d.uf or "", d.nome_arquivo)):
        faltantes = campos_incompletos(doc)
        print(f"  [{doc.uf or '??'}] {doc.sindicato or '??'} — {doc.nome_arquivo}")
        print(f"        Campos ausentes: {', '.join(faltantes)}")
    print()
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    raiz = _raiz_repo()
    registry_path = raiz / args.registry

    registro = carregar(registry_path)
    if not registro:
        print("Registro vazio. Execute 'scan' primeiro.")
        return 0

    imprimir_resumo(list(registro.values()))
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    raiz = _raiz_repo()
    registry_path = raiz / args.registry
    output_path = raiz / args.output

    registro = carregar(registry_path)
    if not registro:
        print("Registro vazio. Execute 'scan' primeiro.")
        return 0

    total = len(registro)
    print(f"Processando {total} documento(s) do registro...")

    textos = processar_extracao(registro, raiz)

    salvar_textos(output_path, textos)
    print(f"Textos extraídos salvos em '{output_path}'.")

    imprimir_relatorio_extracao(textos)
    return 0


def cmd_check_ocr_env(args: argparse.Namespace) -> int:
    resultado = verificar_ambiente_ocr()
    imprimir_resultado_verificacao(resultado)
    return 0 if resultado.ok else 1


def cmd_ocr(args: argparse.Namespace) -> int:
    resultado = verificar_ambiente_ocr()
    if not resultado.ok:
        imprimir_resultado_verificacao(resultado)
        return 1

    from datetime import datetime, timezone
    from src.services.ocr import ocr_pdf

    raiz = _raiz_repo()
    input_path = raiz / args.input
    output_path = raiz / args.output

    if not input_path.exists():
        print(
            f"Arquivo de extração não encontrado: '{input_path}'. "
            "Execute 'extract' primeiro.",
            file=sys.stderr,
        )
        return 1

    todos = carregar_textos(input_path)
    elegíveis = [t for t in todos if t.status == "sem_texto_extraivel"]

    if not elegíveis:
        print("Nenhum documento elegível para OCR (status 'sem_texto_extraivel').")
        return 0

    print(f"Executando OCR em {len(elegíveis)} documento(s)...")

    resultados_ocr: list = []
    for doc in elegíveis:
        pdf_path = raiz / doc.caminho
        texto, status = ocr_pdf(pdf_path)
        agora = datetime.now(tz=timezone.utc).isoformat()
        resultados_ocr.append(TextoExtraido(
            caminho=doc.caminho,
            nome_arquivo=doc.nome_arquivo,
            uf=doc.uf,
            sindicato=doc.sindicato,
            tipo_documento=doc.tipo_documento,
            ano_referencia=doc.ano_referencia,
            texto=texto,
            num_caracteres=len(texto),
            status=status,
            data_processamento=agora,
        ))
        icone = "✔" if status == "extraido_via_ocr" else "✘"
        print(f"  {icone} [{status}] {doc.nome_arquivo or doc.caminho}")

    salvar_textos(output_path, resultados_ocr)
    print(f"\nResultados salvos em '{output_path}'.")

    imprimir_relatorio_ocr(resultados_ocr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src",
        description="Registro de documentos sindicais (CCTs e correlatos).",
    )
    parser.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY,
        metavar="PATH",
        help=f"Caminho do arquivo de registro JSON (padrão: {DEFAULT_REGISTRY})",
    )

    sub = parser.add_subparsers(dest="comando", required=True)

    # scan
    p_scan = sub.add_parser("scan", help="Varre a pasta CCT/ e atualiza o registro")
    p_scan.add_argument(
        "--cct-dir",
        default=DEFAULT_CCT_DIR,
        metavar="DIR",
        help=f"Pasta raiz da estrutura CCT (padrão: {DEFAULT_CCT_DIR})",
    )
    p_scan.add_argument(
        "--responsavel",
        default=None,
        metavar="NOME",
        help="Nome do responsável pela inclusão dos documentos",
    )
    p_scan.set_defaults(func=cmd_scan)

    # list
    p_list = sub.add_parser("list", help="Exibe lista consolidada de documentos")
    p_list.add_argument(
        "--invalid-only",
        action="store_true",
        help="Exibe apenas documentos inválidos para extração",
    )
    p_list.add_argument(
        "--incomplete-only",
        action="store_true",
        help="Exibe apenas documentos com campos de cadastro incompletos",
    )
    p_list.set_defaults(func=cmd_list)

    # show-incomplete
    p_inc = sub.add_parser(
        "show-incomplete",
        help="Exibe documentos com campos de cadastro incompletos",
    )
    p_inc.set_defaults(func=cmd_show_incomplete)

    # summary
    p_sum = sub.add_parser("summary", help="Exibe resumo estatístico do registro")
    p_sum.set_defaults(func=cmd_summary)

    # extract
    p_ext = sub.add_parser(
        "extract",
        help="Extrai texto bruto dos PDFs cadastrados no registro",
    )
    p_ext.add_argument(
        "--output",
        default=DEFAULT_EXTRACTION_OUTPUT,
        metavar="PATH",
        help=f"Caminho do arquivo de saída JSON (padrão: {DEFAULT_EXTRACTION_OUTPUT})",
    )
    p_ext.set_defaults(func=cmd_extract)

    # ocr
    p_ocr = sub.add_parser(
        "ocr",
        help="Executa OCR nos PDFs classificados como sem_texto_extraivel",
    )
    p_ocr.add_argument(
        "--input",
        default=DEFAULT_EXTRACTION_OUTPUT,
        metavar="PATH",
        help=f"Arquivo JSON de extração gerado pelo comando 'extract' (padrão: {DEFAULT_EXTRACTION_OUTPUT})",
    )
    p_ocr.add_argument(
        "--output",
        default=DEFAULT_OCR_OUTPUT,
        metavar="PATH",
        help=f"Caminho do arquivo de saída JSON com resultados do OCR (padrão: {DEFAULT_OCR_OUTPUT})",
    )
    p_ocr.set_defaults(func=cmd_ocr)

    # check-ocr-env
    p_check = sub.add_parser(
        "check-ocr-env",
        help="Verifica se o ambiente possui as dependências necessárias para OCR",
    )
    p_check.set_defaults(func=cmd_check_ocr_env)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
