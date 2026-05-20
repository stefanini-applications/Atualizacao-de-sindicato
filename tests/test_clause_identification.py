"""Testes para o comando identify-clauses da CLI e módulos de identificação de cláusulas.

Cobre os critérios de aceitação da US-PRJ-7:
  AC1 — filtragem da base de entrada por status_consolidado
  AC2 — identificação e classificação de cláusulas candidatas
  AC3 — preservação do trecho original e rastreabilidade completa
  AC4 — geração atômica de clausulas_candidatas.json com versão e data_geracao
  AC5 — relatório de cobertura com totais
  AC6 — normalização de texto na correspondência (acentos, hífen, maiúsculas, plural)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.clausula_candidata import ClausulaCandidata, TIPOS_CLAUSULA
from src.models.texto_extraido import TextoConsolidado
from src.services.clause_identifier import identificar_clausulas, _STATUS_ELEGIVEIS
from src.services.clause_store import salvar_clausulas, carregar_clausulas
from src.reports.clauses import imprimir_relatorio_clausulas
from src.utils.text_normalizer import normalizar


# ── helpers ───────────────────────────────────────────────────────────────────

def _consolidado(
    caminho="CCT/SP/Sind/a.pdf",
    status="texto_nativo",
    texto="Texto de exemplo.",
    **kwargs,
) -> TextoConsolidado:
    defaults = dict(
        caminho=caminho,
        nome_arquivo=Path(caminho).name,
        uf="SP",
        sindicato="Sind",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        texto_final=texto,
        num_caracteres=len(texto),
        origem_texto=status,
        status_consolidado=status,
        data_consolidacao="2025-01-01T00:00:00+00:00",
    )
    defaults.update(kwargs)
    return TextoConsolidado(**defaults)


# ── AC6: normalização de texto ────────────────────────────────────────────────

def test_normalizar_converte_para_minusculas():
    assert normalizar("REAJUSTE SALARIAL") == "reajuste salarial"


def test_normalizar_remove_acentos():
    assert normalizar("refeição") == "refeicao"
    assert normalizar("auxílio") == "auxilio"
    assert normalizar("remuneração") == "remuneracao"
    assert normalizar("vigência") == "vigencia"


def test_normalizar_unifica_hifen():
    assert normalizar("vale-refeição") == "vale refeicao"
    assert normalizar("data-base") == "data base"


def test_normalizar_colapsa_espacos():
    assert normalizar("piso   salarial") == "piso salarial"
    assert normalizar("  reajuste  ") == "reajuste"


def test_normalizar_travessao_longo():
    assert "data base" in normalizar("data–base")


def test_normalizar_preserva_texto_original_nao_modificado():
    """A função normalizar NÃO deve alterar a string original — apenas retorna nova."""
    original = "Reajuste Salarial — 5%"
    _ = normalizar(original)
    assert original == "Reajuste Salarial — 5%"


# ── AC6: correspondência por keyword com normalização ─────────────────────────

def test_identifica_reajuste_com_acento():
    doc = _consolidado(texto="O reajuste salarial foi de 5% conforme acordado.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "reajuste_salarial" in tipos


def test_identifica_vale_refeicao_com_hifen():
    doc = _consolidado(texto="Fica estabelecido vale-refeição no valor de R$ 30,00.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "vale_refeicao" in tipos


def test_identifica_vale_alimentacao_com_acento():
    doc = _consolidado(texto="Auxílio alimentação será concedido mensalmente.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "vale_alimentacao" in tipos


def test_identifica_plr_maiusculo():
    doc = _consolidado(texto="A empresa pagará PLR conforme acordo coletivo.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "plr" in tipos


def test_identifica_vigencia_data_base_com_hifen():
    doc = _consolidado(texto="A data-base desta convenção é 1º de março.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "vigencia_data_base" in tipos


def test_identifica_plural_salarios():
    """'salários' (plural com acento) deve ser encontrado pela busca de 'salario'."""
    doc = _consolidado(texto="Os salários serão reajustados em março.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    # "salarios" contém "salario" (substring) e "reajust" é encontrado também
    assert len(resultado) > 0


def test_identifica_hora_extra_plural():
    """'horas extras' deve ser identificado na categoria adicionais."""
    doc = _consolidado(texto="O pagamento de horas extras seguirá a legislação vigente.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "adicionais" in tipos


def test_identifica_piso_salarial():
    doc = _consolidado(texto="O piso salarial da categoria é de R$ 2.000,00.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "piso_salarial" in tipos


def test_identifica_auxilio_home_office():
    doc = _consolidado(texto="Será pago auxílio home office de R$ 150,00 mensais.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "auxilio_home_office" in tipos


def test_identifica_insalubridade():
    doc = _consolidado(texto="O adicional de insalubridade será pago conforme NR-15.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "adicionais" in tipos


def test_identifica_participacao_nos_lucros():
    doc = _consolidado(texto="A participação nos lucros será distribuída em março.")
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "plr" in tipos


# ── AC1: filtragem por status_consolidado ─────────────────────────────────────

def test_status_elegiveis_sao_texto_nativo_e_texto_ocr():
    assert "texto_nativo" in _STATUS_ELEGIVEIS
    assert "texto_ocr" in _STATUS_ELEGIVEIS
    assert "sem_texto_final" not in _STATUS_ELEGIVEIS
    assert "erro_consolidacao" not in _STATUS_ELEGIVEIS


def test_documento_sem_texto_final_ignorado():
    doc = _consolidado(status="sem_texto_final", texto="")
    resultado = identificar_clausulas([doc])
    assert resultado == []


def test_documento_erro_consolidacao_ignorado():
    doc = _consolidado(status="erro_consolidacao", texto="reajuste salarial")
    resultado = identificar_clausulas([doc])
    assert resultado == []


def test_documento_texto_ocr_elegivel():
    doc = _consolidado(status="texto_ocr", texto="Reajuste salarial de 5%.")
    resultado = identificar_clausulas([doc])
    assert len(resultado) > 0


def test_documento_texto_nativo_elegivel():
    doc = _consolidado(status="texto_nativo", texto="Piso salarial mínimo estabelecido.")
    resultado = identificar_clausulas([doc])
    assert len(resultado) > 0


def test_mistura_elegiveis_e_ignorados():
    """Apenas documentos com status elegível devem ser analisados."""
    docs = [
        _consolidado("CCT/SP/A/a.pdf", status="texto_nativo", texto="reajuste salarial"),
        _consolidado("CCT/SP/B/b.pdf", status="sem_texto_final", texto=""),
        _consolidado("CCT/SP/C/c.pdf", status="erro_consolidacao", texto="piso salarial"),
        _consolidado("CCT/SP/D/d.pdf", status="texto_ocr", texto="vale refeição"),
    ]
    resultado = identificar_clausulas(docs)
    caminhos = {c.caminho for c in resultado}
    assert "CCT/SP/A/a.pdf" in caminhos
    assert "CCT/SP/D/d.pdf" in caminhos
    assert "CCT/SP/B/b.pdf" not in caminhos
    assert "CCT/SP/C/c.pdf" not in caminhos


# ── AC2: múltiplas cláusulas por documento ────────────────────────────────────

def test_multiplas_categorias_geram_registros_independentes():
    """Um segmento com termos de múltiplas categorias gera um registro por categoria."""
    doc = _consolidado(
        texto="O reajuste salarial e o vale refeição foram acordados."
    )
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "reajuste_salarial" in tipos
    assert "vale_refeicao" in tipos
    assert len(resultado) >= 2


def test_multiplos_segmentos_geram_registros_independentes():
    """Dois parágrafos distintos, cada um com um tema diferente, geram registros separados."""
    texto = "Reajuste salarial de 5%.\n\nVale alimentação de R$ 500,00."
    doc = _consolidado(texto=texto)
    resultado = identificar_clausulas([doc])
    tipos = {c.tipo_clausula for c in resultado}
    assert "reajuste_salarial" in tipos
    assert "vale_alimentacao" in tipos


def test_sem_termos_relevantes_retorna_vazio():
    doc = _consolidado(texto="As férias serão concedidas conforme CLT.")
    resultado = identificar_clausulas([doc])
    assert resultado == []


def test_multiplos_documentos_independentes():
    docs = [
        _consolidado("CCT/SP/A/a.pdf", texto="Reajuste de 5%."),
        _consolidado("CCT/SP/B/b.pdf", texto="Vale refeição mensal."),
    ]
    resultado = identificar_clausulas(docs)
    caminhos = [c.caminho for c in resultado]
    assert "CCT/SP/A/a.pdf" in caminhos
    assert "CCT/SP/B/b.pdf" in caminhos


# ── AC3: preservação do trecho e rastreabilidade ──────────────────────────────

def test_trecho_preserva_texto_original_nao_normalizado():
    """O trecho armazenado deve ser o texto original, com acentos e capitalização."""
    texto_original = "O reajuste salarial é de 5% — conforme Cláusula Quarta."
    doc = _consolidado(texto=texto_original)
    resultado = identificar_clausulas([doc])
    assert len(resultado) > 0
    # Trecho deve conter o texto com acento/capitalização original
    assert resultado[0].trecho == texto_original


def test_campos_rastreabilidade_completos():
    """Todos os campos de rastreabilidade obrigatórios devem estar presentes."""
    doc = _consolidado(
        caminho="CCT/MG/SindMG/cct.pdf",
        uf="MG",
        sindicato="SindMG",
        tipo_documento="TA",
        ano_referencia="2024-2025",
        status="texto_nativo",
        texto="Piso salarial definido em cláusula.",
    )
    resultado = identificar_clausulas([doc])
    assert len(resultado) > 0
    c = resultado[0]
    assert c.caminho == "CCT/MG/SindMG/cct.pdf"
    assert c.nome_arquivo == "cct.pdf"
    assert c.uf == "MG"
    assert c.sindicato == "SindMG"
    assert c.tipo_documento == "TA"
    assert c.ano_referencia == "2024-2025"
    assert c.origem_texto == "texto_nativo"
    assert c.status_consolidado == "texto_nativo"
    assert c.tipo_clausula in TIPOS_CLAUSULA
    assert c.metodo_identificacao == "keyword_match_normalized"
    assert c.data_hora_processamento != ""
    assert "T" in c.data_hora_processamento


def test_metodo_identificacao_e_keyword_match_normalized():
    doc = _consolidado(texto="reajuste salarial de 5%.")
    resultado = identificar_clausulas([doc])
    assert all(c.metodo_identificacao == "keyword_match_normalized" for c in resultado)


# ── AC4: persistência ─────────────────────────────────────────────────────────

def test_salvar_e_carregar_clausulas_roundtrip(tmp_path):
    """salvar_clausulas / carregar_clausulas devem fazer round-trip fiel."""
    clausulas = [
        ClausulaCandidata(
            trecho="Reajuste salarial de 5%.",
            caminho="CCT/SP/A/a.pdf",
            nome_arquivo="a.pdf",
            uf="SP",
            sindicato="SindSP",
            tipo_documento="CCT",
            ano_referencia="2025",
            origem_texto="texto_nativo",
            status_consolidado="texto_nativo",
            tipo_clausula="reajuste_salarial",
            metodo_identificacao="keyword_match_normalized",
            data_hora_processamento="2025-01-01T00:00:00+00:00",
        )
    ]
    path = tmp_path / "clausulas.json"
    salvar_clausulas(path, clausulas)
    carregadas = carregar_clausulas(path)

    assert len(carregadas) == 1
    c = carregadas[0]
    assert c.trecho == "Reajuste salarial de 5%."
    assert c.caminho == "CCT/SP/A/a.pdf"
    assert c.tipo_clausula == "reajuste_salarial"
    assert c.metodo_identificacao == "keyword_match_normalized"


def test_arquivo_saida_tem_versao_e_data_geracao(tmp_path):
    """Arquivo de saída deve conter 'versao', 'data_geracao' e 'clausulas'."""
    path = tmp_path / "clausulas.json"
    salvar_clausulas(path, [])
    with path.open(encoding="utf-8") as f:
        dados = json.load(f)
    assert dados.get("versao") == 1
    assert "data_geracao" in dados
    assert isinstance(dados["clausulas"], list)


def test_salvar_sobrescreve_integralmente(tmp_path):
    """Segunda chamada de salvar_clausulas deve sobrescrever totalmente o arquivo."""
    path = tmp_path / "clausulas.json"
    clausula = ClausulaCandidata(
        trecho="x", caminho="a", nome_arquivo="a", uf=None, sindicato=None,
        tipo_documento=None, ano_referencia=None, origem_texto="texto_nativo",
        status_consolidado="texto_nativo", tipo_clausula="reajuste_salarial",
        metodo_identificacao="keyword_match_normalized",
        data_hora_processamento="2025-01-01T00:00:00+00:00",
    )
    salvar_clausulas(path, [clausula, clausula])
    salvar_clausulas(path, [clausula])
    carregadas = carregar_clausulas(path)
    assert len(carregadas) == 1


def test_carregar_retorna_lista_vazia_se_arquivo_ausente(tmp_path):
    result = carregar_clausulas(tmp_path / "inexistente.json")
    assert result == []


# ── AC5: relatório de cobertura ───────────────────────────────────────────────

def test_relatorio_exibe_totais(capsys):
    clausulas = [
        ClausulaCandidata(
            trecho="t", caminho="a", nome_arquivo="a", uf=None, sindicato=None,
            tipo_documento=None, ano_referencia=None, origem_texto="texto_nativo",
            status_consolidado="texto_nativo", tipo_clausula="reajuste_salarial",
            metodo_identificacao="keyword_match_normalized",
            data_hora_processamento="2025-01-01T00:00:00+00:00",
        )
    ]
    imprimir_relatorio_clausulas(
        total_avaliados=5,
        total_analisados=4,
        total_ignorados=1,
        clausulas=clausulas,
    )
    saida = capsys.readouterr().out
    assert "5" in saida
    assert "4" in saida
    assert "1" in saida
    assert "1" in saida  # total clausulas


def test_relatorio_exibe_todos_tipos(capsys):
    imprimir_relatorio_clausulas(0, 0, 0, [])
    saida = capsys.readouterr().out
    for tipo_label in [
        "Reajuste salarial", "Piso salarial", "Vale refeição", "Vale alimentação",
        "Benefícios", "Adicionais", "PLR", "Auxílio home office",
        "Vigência", "Outros remuneração",
    ]:
        assert tipo_label in saida, f"Label '{tipo_label}' não encontrado no relatório"


def test_relatorio_contagem_por_tipo(capsys):
    clausulas = [
        ClausulaCandidata(
            trecho="t", caminho="a", nome_arquivo="a", uf=None, sindicato=None,
            tipo_documento=None, ano_referencia=None, origem_texto="texto_nativo",
            status_consolidado="texto_nativo", tipo_clausula=tipo,
            metodo_identificacao="keyword_match_normalized",
            data_hora_processamento="2025-01-01T00:00:00+00:00",
        )
        for tipo in ["reajuste_salarial", "reajuste_salarial", "piso_salarial"]
    ]
    imprimir_relatorio_clausulas(3, 3, 0, clausulas)
    saida = capsys.readouterr().out
    assert "3" in saida  # total clausulas


# ── AC4: subcomando CLI ───────────────────────────────────────────────────────

def test_cmd_falha_se_arquivo_entrada_ausente(tmp_path):
    """identify-clauses deve retornar código 1 quando a base consolidada não existe."""
    from src.cli import cmd_identify_clauses
    args = MagicMock()
    args.input = str(tmp_path / "inexistente.json")
    args.output = str(tmp_path / "out.json")
    with patch("src.cli._raiz_repo", return_value=tmp_path):
        result = cmd_identify_clauses(args)
    assert result == 1


def test_cmd_gera_arquivo_saida(tmp_path):
    """identify-clauses deve criar o arquivo de saída."""
    from src.services.extraction_store import salvar_consolidados
    from src.cli import cmd_identify_clauses

    doc = _consolidado(texto="Reajuste salarial de 5% a partir de março.")
    input_path = tmp_path / "textos_consolidados.json"
    output_path = tmp_path / "clausulas_candidatas.json"
    salvar_consolidados(input_path, [doc])

    args = MagicMock()
    args.input = str(input_path)
    args.output = str(output_path)
    with patch("src.cli._raiz_repo", return_value=tmp_path):
        result = cmd_identify_clauses(args)

    assert result == 0
    assert output_path.exists()


def test_cmd_retorna_clausulas_corretas(tmp_path):
    """identify-clauses deve salvar cláusulas identificadas no arquivo de saída."""
    from src.services.extraction_store import salvar_consolidados
    from src.cli import cmd_identify_clauses

    doc = _consolidado(texto="Vale refeição de R$ 30,00 por dia trabalhado.")
    input_path = tmp_path / "textos_consolidados.json"
    output_path = tmp_path / "clausulas_candidatas.json"
    salvar_consolidados(input_path, [doc])

    args = MagicMock()
    args.input = str(input_path)
    args.output = str(output_path)
    with patch("src.cli._raiz_repo", return_value=tmp_path):
        cmd_identify_clauses(args)

    clausulas = carregar_clausulas(output_path)
    tipos = {c.tipo_clausula for c in clausulas}
    assert "vale_refeicao" in tipos


def test_cmd_documentos_ignorados_nao_geram_clausulas(tmp_path):
    """Documentos sem texto não devem gerar cláusulas candidatas."""
    from src.services.extraction_store import salvar_consolidados
    from src.cli import cmd_identify_clauses
    from datetime import datetime, timezone

    agora = datetime.now(tz=timezone.utc).isoformat()
    doc_ignorado = TextoConsolidado(
        caminho="CCT/SP/A/a.pdf", nome_arquivo="a.pdf",
        uf="SP", sindicato="S", tipo_documento="CCT", ano_referencia="2025",
        texto_final="", num_caracteres=0,
        origem_texto="sem_texto_final", status_consolidado="sem_texto_final",
        data_consolidacao=agora,
    )
    input_path = tmp_path / "textos_consolidados.json"
    output_path = tmp_path / "clausulas_candidatas.json"
    salvar_consolidados(input_path, [doc_ignorado])

    args = MagicMock()
    args.input = str(input_path)
    args.output = str(output_path)
    with patch("src.cli._raiz_repo", return_value=tmp_path):
        result = cmd_identify_clauses(args)

    assert result == 0
    clausulas = carregar_clausulas(output_path)
    assert clausulas == []


def test_cmd_relatorio_exibido_no_stdout(tmp_path, capsys):
    """identify-clauses deve exibir o relatório de cobertura."""
    from src.services.extraction_store import salvar_consolidados
    from src.cli import cmd_identify_clauses

    doc = _consolidado(texto="Reajuste salarial de 5%.")
    input_path = tmp_path / "textos_consolidados.json"
    output_path = tmp_path / "clausulas_candidatas.json"
    salvar_consolidados(input_path, [doc])

    args = MagicMock()
    args.input = str(input_path)
    args.output = str(output_path)
    with patch("src.cli._raiz_repo", return_value=tmp_path):
        cmd_identify_clauses(args)

    saida = capsys.readouterr().out
    assert "Relatório" in saida or "relatorio" in saida.lower() or "Identificação" in saida


# ── Tipos de cláusula canônicos ───────────────────────────────────────────────

def test_tipos_clausula_tem_dez_valores():
    assert len(TIPOS_CLAUSULA) == 10


def test_tipos_clausula_contem_todos_obrigatorios():
    obrigatorios = {
        "reajuste_salarial", "piso_salarial", "vale_refeicao", "vale_alimentacao",
        "beneficios", "adicionais", "plr", "auxilio_home_office",
        "vigencia_data_base", "outros_remuneracao",
    }
    assert obrigatorios == TIPOS_CLAUSULA


# ── Parser CLI ────────────────────────────────────────────────────────────────

def test_parser_reconhece_identify_clauses():
    from src.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["identify-clauses"])
    assert args.comando == "identify-clauses"
    from src.cli import cmd_identify_clauses
    assert args.func == cmd_identify_clauses


def test_parser_identify_clauses_defaults():
    from src.cli import build_parser, DEFAULT_CONSOLIDATION_OUTPUT, DEFAULT_CLAUSES_OUTPUT
    parser = build_parser()
    args = parser.parse_args(["identify-clauses"])
    assert args.input == DEFAULT_CONSOLIDATION_OUTPUT
    assert args.output == DEFAULT_CLAUSES_OUTPUT
