"""Interface de linha de comando para o registro de documentos sindicais.

Comandos disponíveis:
  scan            Varre a pasta CCT/ e atualiza o registro
  list            Exibe lista consolidada de documentos
  show-incomplete Exibe documentos com campos de cadastro incompletos
  summary         Exibe resumo estatístico do registro
  extract         Extrai texto bruto dos PDFs cadastrados no registro
  ocr             Executa OCR nos PDFs classificados como sem_texto_extraivel
  check-ocr-env   Verifica se o ambiente possui as dependências necessárias para OCR
  preview-pricing-update  Gera prévia de correspondência entre reajustes aprovados e base de pricing
"""

import argparse
import sys
from pathlib import Path

from src.services.scanner import varrer_pasta_cct
from src.services.registry import carregar, salvar, upsert
from src.services.extractor import processar_extracao
from src.services.extraction_store import salvar_textos, carregar_textos, salvar_consolidados, carregar_consolidados
from src.reports.consolidated import imprimir_lista, imprimir_resumo
from src.reports.extraction import imprimir_relatorio_extracao
from src.reports.ocr import imprimir_relatorio_ocr
from src.reports.consolidation import imprimir_relatorio_consolidacao
from src.services.validator import campos_criticos_ausentes_ou_invalidos, campos_incompletos
from src.services.env_checker import verificar_ambiente_ocr, imprimir_resultado_verificacao
from src.models.texto_extraido import TextoExtraido

DEFAULT_CCT_DIR = "CCT"
DEFAULT_REGISTRY = "data/registro_documentos.json"
DEFAULT_EXTRACTION_OUTPUT = "data/textos_extraidos.json"
DEFAULT_OCR_OUTPUT = "data/textos_ocr.json"
DEFAULT_CONSOLIDATION_OUTPUT = "data/textos_consolidados.json"
DEFAULT_CLAUSES_OUTPUT = "data/clausulas_candidatas.json"
DEFAULT_ADJUSTMENTS_OUTPUT = "data/reajustes_extraidos.json"
DEFAULT_VALIDATION_OUTPUT = "data/reajustes_para_validacao.json"
DEFAULT_APPROVED_OUTPUT = "data/reajustes_aprovados.json"
DEFAULT_PRICING_INPUT = "data/base_pricing.xlsx"
DEFAULT_PREVIEW_OUTPUT = "data/preview_atualizacao_pricing.xlsx"


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


def cmd_consolidate_texts(args: argparse.Namespace) -> int:
    from src.services.consolidator import consolidar_textos

    raiz = _raiz_repo()
    native_path = raiz / args.input_native
    ocr_path = raiz / args.input_ocr
    output_path = raiz / args.output

    if not native_path.exists():
        print(
            f"Erro: arquivo de extração nativa não encontrado: '{native_path}'. "
            "Execute 'extract' primeiro.",
            file=sys.stderr,
        )
        return 1

    textos_nativos = carregar_textos(native_path)

    ocr_disponivel = ocr_path.exists()
    textos_ocr = carregar_textos(ocr_path) if ocr_disponivel else []

    if not ocr_disponivel:
        print(f"Base OCR não encontrada — complementação via OCR ignorada.")

    print(f"Consolidando {len(textos_nativos)} documento(s)...")

    consolidados = consolidar_textos(textos_nativos, textos_ocr)

    salvar_consolidados(output_path, consolidados)
    print(f"Base consolidada salva em '{output_path}'.")

    imprimir_relatorio_consolidacao(consolidados, ocr_disponivel=ocr_disponivel)
    return 0


def cmd_identify_clauses(args: argparse.Namespace) -> int:
    from src.services.clause_identifier import identificar_clausulas, _STATUS_ELEGIVEIS
    from src.services.clause_store import salvar_clausulas
    from src.reports.clauses import imprimir_relatorio_clausulas

    raiz = _raiz_repo()
    input_path = raiz / args.input
    output_path = raiz / args.output

    if not input_path.exists():
        print(
            f"Erro: base consolidada não encontrada: '{input_path}'. "
            "Execute 'consolidate-texts' primeiro.",
            file=sys.stderr,
        )
        return 1

    consolidados = carregar_consolidados(input_path)

    total_avaliados = len(consolidados)
    total_analisados = sum(
        1 for d in consolidados if d.status_consolidado in _STATUS_ELEGIVEIS
    )
    total_ignorados = total_avaliados - total_analisados

    print(f"Identificando cláusulas em {total_analisados} documento(s) elegível(is)...")

    clausulas = identificar_clausulas(consolidados)

    salvar_clausulas(output_path, clausulas)
    print(f"Cláusulas candidatas salvas em '{output_path}'.")

    imprimir_relatorio_clausulas(total_avaliados, total_analisados, total_ignorados, clausulas)
    return 0


def cmd_extract_adjustments(args: argparse.Namespace) -> int:
    from src.services.adjustment_extractor import extrair_reajustes, _TIPOS_ESCOPO
    from src.services.adjustment_store import salvar_reajustes
    from src.services.clause_store import carregar_clausulas
    from src.reports.adjustments import imprimir_relatorio_reajustes

    raiz = _raiz_repo()
    input_path = raiz / args.input
    output_path = raiz / args.output

    if not input_path.exists():
        print(
            f"Erro: cláusulas candidatas não encontradas: '{input_path}'. "
            "Execute 'identify-clauses' primeiro.",
            file=sys.stderr,
        )
        return 1

    clausulas = carregar_clausulas(input_path)

    total_avaliadas = len(clausulas)
    total_escopo = sum(1 for c in clausulas if c.tipo_clausula in _TIPOS_ESCOPO)
    total_ignoradas_categoria = total_avaliadas - total_escopo

    print(f"Extraindo reajustes de {total_escopo} cláusula(s) no escopo...")

    reajustes = extrair_reajustes(clausulas)

    salvar_reajustes(output_path, reajustes)
    print(f"Reajustes extraídos salvos em '{output_path}'.")

    imprimir_relatorio_reajustes(
        total_avaliadas, total_escopo, total_ignoradas_categoria, reajustes
    )
    return 0


def cmd_validate_adjustments(args: argparse.Namespace) -> int:
    from src.services.adjustment_store import carregar_reajustes
    from src.services.validation_preparer import preparar_para_validacao
    from src.services.validation_store import salvar_para_validacao
    from src.reports.validation import imprimir_relatorio_validacao

    raiz = _raiz_repo()
    input_path = raiz / args.input
    output_path = raiz / args.output

    if not input_path.exists():
        print(
            f"Erro: reajustes extraídos não encontrados: '{input_path}'. "
            "Execute 'extract-adjustments' primeiro.",
            file=sys.stderr,
        )
        return 1

    reajustes = carregar_reajustes(input_path)

    print(f"Preparando {len(reajustes)} registro(s) para validação humana...")

    registros = preparar_para_validacao(reajustes)

    salvar_para_validacao(output_path, registros)
    print(f"Registros para validação salvos em '{output_path}'.")

    imprimir_relatorio_validacao(registros)
    return 0


def cmd_review_adjustments(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

    from src.services.validation_store import carregar_para_validacao, salvar_para_validacao
    from src.services.manual_review import revisar_registros
    from src.reports.manual_review import imprimir_relatorio_revisao

    raiz = _raiz_repo()
    input_path = raiz / args.input
    output_path = raiz / args.output

    if not input_path.exists():
        print(
            f"Erro: arquivo de validação não encontrado: '{input_path}'. "
            "Execute 'validate-adjustments' primeiro.",
            file=sys.stderr,
        )
        return 1

    registros = carregar_para_validacao(input_path)
    print(f"Revisando {len(registros)} registro(s)...")

    timestamp = datetime.now(tz=timezone.utc).isoformat()
    try:
        revisados = revisar_registros(registros, args.responsavel, timestamp)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    salvar_para_validacao(output_path, revisados)
    print(f"Registros revisados salvos em '{output_path}'.")

    imprimir_relatorio_revisao(revisados)
    return 0


def cmd_generate_approved_adjustments(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

    from src.services.validation_store import carregar_para_validacao
    from src.services.approval_generator import gerar_reajustes_aprovados
    from src.services.approved_store import salvar_aprovados
    from src.reports.approval import imprimir_relatorio_aprovacao

    raiz = _raiz_repo()
    input_path = raiz / args.input
    output_path = raiz / args.output

    if not input_path.exists():
        print(
            f"Erro: arquivo de validação não encontrado: '{input_path}'. "
            "Execute 'validate-adjustments' primeiro.",
            file=sys.stderr,
        )
        return 1

    registros = carregar_para_validacao(input_path)
    total_avaliados = len(registros)

    timestamp = datetime.now(tz=timezone.utc).isoformat()
    aprovados, total_com_correcao = gerar_reajustes_aprovados(registros, timestamp)

    total_aprovados = len(aprovados)
    total_ignorados = total_avaliados - total_aprovados

    salvar_aprovados(output_path, aprovados)
    print(f"Reajustes aprovados salvos em '{output_path}'.")

    imprimir_relatorio_aprovacao(total_avaliados, total_aprovados, total_ignorados, total_com_correcao)

    if total_aprovados == 0:
        print(
            "Aviso: nenhum registro aprovado encontrado. "
            "Execute 'review-adjustments' para aprovar registros antes de usar esta base.",
            file=sys.stderr,
        )
        return 1

    return 0


def cmd_preview_pricing_update(args: argparse.Namespace) -> int:
    from src.services.approved_store import carregar_aprovados
    from src.services.pricing_reader import carregar_base_pricing
    from src.services.pricing_preview import gerar_preview
    from src.services.preview_writer import salvar_preview
    from src.reports.preview_pricing import imprimir_relatorio_preview

    raiz = _raiz_repo()
    adjustments_path = raiz / args.adjustments
    pricing_path = raiz / args.pricing
    output_path = raiz / args.output

    # AC1: validar existência dos arquivos de entrada
    ausentes = []
    if not adjustments_path.exists():
        ausentes.append(str(adjustments_path))
    if not pricing_path.exists():
        ausentes.append(str(pricing_path))

    if ausentes:
        for arq in ausentes:
            print(f"Erro: arquivo não encontrado: '{arq}'", file=sys.stderr)
        return 1

    aprovados = carregar_aprovados(adjustments_path)

    try:
        linhas, colunas, col_uf, col_sindicato, col_ano = carregar_base_pricing(pricing_path)
    except ValueError as exc:
        print(f"Erro ao carregar base de pricing: {exc}", file=sys.stderr)
        return 1

    total_avaliadas = len(linhas)
    print(f"Cruzando {total_avaliadas} linha(s) da base de pricing com "
          f"{len(aprovados)} reajuste(s) aprovado(s)...")

    preview = gerar_preview(linhas, aprovados, col_uf, col_sindicato, col_ano)

    salvar_preview(output_path, preview, colunas)
    print(f"Prévia salva em '{output_path}'.")

    contagens: dict = {}
    for linha in preview:
        contagens[linha.status_aplicacao] = contagens.get(linha.status_aplicacao, 0) + 1

    imprimir_relatorio_preview(total_avaliadas, contagens)
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

    # consolidate-texts
    p_cons = sub.add_parser(
        "consolidate-texts",
        help="Consolida a base nativa e OCR em uma fonte única rastreável",
    )
    p_cons.add_argument(
        "--input-native",
        default=DEFAULT_EXTRACTION_OUTPUT,
        metavar="PATH",
        help=f"Arquivo JSON de extração nativa (padrão: {DEFAULT_EXTRACTION_OUTPUT})",
    )
    p_cons.add_argument(
        "--input-ocr",
        default=DEFAULT_OCR_OUTPUT,
        metavar="PATH",
        help=f"Arquivo JSON de resultados OCR (padrão: {DEFAULT_OCR_OUTPUT})",
    )
    p_cons.add_argument(
        "--output",
        default=DEFAULT_CONSOLIDATION_OUTPUT,
        metavar="PATH",
        help=f"Caminho do arquivo de saída JSON (padrão: {DEFAULT_CONSOLIDATION_OUTPUT})",
    )
    p_cons.set_defaults(func=cmd_consolidate_texts)

    # identify-clauses
    p_ident = sub.add_parser(
        "identify-clauses",
        help="Identifica cláusulas salariais e de benefícios na base consolidada",
    )
    p_ident.add_argument(
        "--input",
        default=DEFAULT_CONSOLIDATION_OUTPUT,
        metavar="PATH",
        help=f"Base consolidada de entrada JSON (padrão: {DEFAULT_CONSOLIDATION_OUTPUT})",
    )
    p_ident.add_argument(
        "--output",
        default=DEFAULT_CLAUSES_OUTPUT,
        metavar="PATH",
        help=f"Arquivo de saída JSON com cláusulas candidatas (padrão: {DEFAULT_CLAUSES_OUTPUT})",
    )
    p_ident.set_defaults(func=cmd_identify_clauses)

    # extract-adjustments
    p_adj = sub.add_parser(
        "extract-adjustments",
        help="Extrai dados estruturados de reajuste salarial e vigência das cláusulas candidatas",
    )
    p_adj.add_argument(
        "--input",
        default=DEFAULT_CLAUSES_OUTPUT,
        metavar="PATH",
        help=f"Arquivo JSON de cláusulas candidatas (padrão: {DEFAULT_CLAUSES_OUTPUT})",
    )
    p_adj.add_argument(
        "--output",
        default=DEFAULT_ADJUSTMENTS_OUTPUT,
        metavar="PATH",
        help=f"Arquivo de saída JSON com reajustes extraídos (padrão: {DEFAULT_ADJUSTMENTS_OUTPUT})",
    )
    p_adj.set_defaults(func=cmd_extract_adjustments)

    # validate-adjustments
    p_val = sub.add_parser(
        "validate-adjustments",
        help="Classifica cada reajuste extraído com um status de validação inicial",
    )
    p_val.add_argument(
        "--input",
        default=DEFAULT_ADJUSTMENTS_OUTPUT,
        metavar="PATH",
        help=f"Arquivo JSON de reajustes extraídos (padrão: {DEFAULT_ADJUSTMENTS_OUTPUT})",
    )
    p_val.add_argument(
        "--output",
        default=DEFAULT_VALIDATION_OUTPUT,
        metavar="PATH",
        help=f"Arquivo de saída JSON com registros para validação (padrão: {DEFAULT_VALIDATION_OUTPUT})",
    )
    p_val.set_defaults(func=cmd_validate_adjustments)

    # review-adjustments
    p_rev = sub.add_parser(
        "review-adjustments",
        help="Aplica a revisão manual sobre os registros editados pelo operador",
    )
    p_rev.add_argument(
        "--input",
        default=DEFAULT_VALIDATION_OUTPUT,
        metavar="PATH",
        help=f"Arquivo JSON de registros para validação (padrão: {DEFAULT_VALIDATION_OUTPUT})",
    )
    p_rev.add_argument(
        "--output",
        default=DEFAULT_VALIDATION_OUTPUT,
        metavar="PATH",
        help=f"Arquivo de saída JSON revisado (padrão: {DEFAULT_VALIDATION_OUTPUT})",
    )
    p_rev.add_argument(
        "--responsavel",
        required=True,
        metavar="NOME",
        help="Nome do responsável pela revisão (preenchido em responsavel_validacao)",
    )
    p_rev.set_defaults(func=cmd_review_adjustments)

    # generate-approved-adjustments
    p_gen = sub.add_parser(
        "generate-approved-adjustments",
        help="Gera a base final de reajustes aprovados para uso no pricing",
    )
    p_gen.add_argument(
        "--input",
        default=DEFAULT_VALIDATION_OUTPUT,
        metavar="PATH",
        help=f"Arquivo JSON de registros para validação (padrão: {DEFAULT_VALIDATION_OUTPUT})",
    )
    p_gen.add_argument(
        "--output",
        default=DEFAULT_APPROVED_OUTPUT,
        metavar="PATH",
        help=f"Arquivo de saída JSON com reajustes aprovados (padrão: {DEFAULT_APPROVED_OUTPUT})",
    )
    p_gen.set_defaults(func=cmd_generate_approved_adjustments)

    # preview-pricing-update
    p_prev = sub.add_parser(
        "preview-pricing-update",
        help="Gera prévia de correspondência entre reajustes aprovados e base de pricing",
    )
    p_prev.add_argument(
        "--pricing",
        default=DEFAULT_PRICING_INPUT,
        metavar="PATH",
        help=f"Base de pricing (.xlsx) de entrada (padrão: {DEFAULT_PRICING_INPUT})",
    )
    p_prev.add_argument(
        "--adjustments",
        default=DEFAULT_APPROVED_OUTPUT,
        metavar="PATH",
        help=f"Reajustes aprovados (.json) de entrada (padrão: {DEFAULT_APPROVED_OUTPUT})",
    )
    p_prev.add_argument(
        "--output",
        default=DEFAULT_PREVIEW_OUTPUT,
        metavar="PATH",
        help=f"Arquivo de prévia de saída (.xlsx) (padrão: {DEFAULT_PREVIEW_OUTPUT})",
    )
    p_prev.set_defaults(func=cmd_preview_pricing_update)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
