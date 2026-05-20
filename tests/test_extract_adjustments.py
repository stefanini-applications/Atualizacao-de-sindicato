"""Testes para o comando extract-adjustments e módulos de extração estruturada.

Cobre os critérios de aceitação da US-PRJ-8:
  AC1 — filtragem do escopo (apenas reajuste_salarial e vigencia_data_base)
  AC2 — extração de percentual e datas em múltiplos formatos
  AC3 — status da extração por tipo de cláusula
  AC4 — arquivo de saída com rastreabilidade completa e escrita atômica
  AC5 — relatório de extração com totais corretos
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from src.models.clausula_candidata import ClausulaCandidata
from src.models.reajuste_extraido import ReajusteExtraido, STATUS_EXTRACAO
from src.services.adjustment_extractor import (
    extrair_reajustes,
    _extrair_percentual,
    _extrair_campos_vigencia,
    _TIPOS_ESCOPO,
)
from src.services.adjustment_store import salvar_reajustes, carregar_reajustes
from src.reports.adjustments import imprimir_relatorio_reajustes


# ── helpers ───────────────────────────────────────────────────────────────────

def _clausula(
    tipo: str = "reajuste_salarial",
    trecho: str = "Reajuste de 5%.",
    caminho: str = "CCT/SP/Sind/a.pdf",
    **kwargs,
) -> ClausulaCandidata:
    defaults = dict(
        trecho=trecho,
        caminho=caminho,
        nome_arquivo=Path(caminho).name,
        uf="SP",
        sindicato="Sind",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        origem_texto="texto_nativo",
        status_consolidado="texto_nativo",
        tipo_clausula=tipo,
        metodo_identificacao="keyword_match_normalized",
        data_hora_processamento="2025-01-01T00:00:00+00:00",
    )
    defaults.update(kwargs)
    return ClausulaCandidata(**defaults)


# ── AC1: filtragem do escopo ──────────────────────────────────────────────────

def test_ac1_somente_tipos_escopo_geram_registros():
    clausulas = [
        _clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%."),
        _clausula(tipo="vigencia_data_base", trecho="Vigência de 01/05/2025 a 30/04/2026."),
        _clausula(tipo="piso_salarial", trecho="Piso de R$1500."),
        _clausula(tipo="vale_refeicao", trecho="Vale refeição R$30."),
        _clausula(tipo="beneficios", trecho="Benefícios gerais."),
    ]
    resultado = extrair_reajustes(clausulas)
    assert len(resultado) == 2
    tipos = {r.tipo_clausula for r in resultado}
    assert tipos == {"reajuste_salarial", "vigencia_data_base"}


def test_ac1_nenhuma_clausula_escopo_retorna_lista_vazia():
    clausulas = [
        _clausula(tipo="piso_salarial", trecho="Piso."),
        _clausula(tipo="beneficios", trecho="Benefícios."),
    ]
    resultado = extrair_reajustes(clausulas)
    assert resultado == []


def test_ac1_lista_vazia_retorna_lista_vazia():
    assert extrair_reajustes([]) == []


# ── AC2: extração de percentual ───────────────────────────────────────────────

@pytest.mark.parametrize("trecho,esperado_contains", [
    ("Reajuste de 5%.", "5%"),
    ("Correção salarial de 5,00%.", "5,00%"),
    ("Reajuste de 5.00%.", "5.00%"),
    ("Reajuste de 3,83%.", "3,83%"),
    ("Salário reajustado em 12%.", "12%"),
    ("Reajuste de 4,5%.", "4,5%"),
    ("Reajuste de 5 por cento.", "5 por cento"),
    ("Reajuste de 5,00 por cento.", "5,00 por cento"),
    ("Correção de 10 por cento.", "10 por cento"),
])
def test_ac2_percentual_formatos_numericos(trecho, esperado_contains):
    resultado = _extrair_percentual(trecho)
    assert resultado is not None, f"Deveria extrair percentual de: {trecho!r}"
    assert esperado_contains in resultado


def test_ac2_percentual_extenso_cinco_por_cento():
    resultado = _extrair_percentual("O reajuste é de cinco por cento.")
    assert resultado is not None
    assert "cinco" in resultado.lower()
    assert "por cento" in resultado.lower()


def test_ac2_percentual_extenso_dez_por_cento():
    resultado = _extrair_percentual("Correção de dez por cento sobre o salário.")
    assert resultado is not None
    assert "dez" in resultado.lower()


def test_ac2_sem_percentual_retorna_none():
    resultado = _extrair_percentual("Cláusula genérica sem valores.")
    assert resultado is None


def test_ac2_percentual_nao_confunde_cnpj():
    # CNPJ-like strings should not be mistaken for percentages
    resultado = _extrair_percentual("CNPJ: 12.345.678/0001-99.")
    assert resultado is None


# ── AC2: extração de datas ────────────────────────────────────────────────────

def test_ac2_data_slash_vigencia_inicio_fim():
    db, ini, fim = _extrair_campos_vigencia(
        "Vigência de 01/05/2025 a 30/04/2026."
    )
    assert ini == "2025-05-01"
    assert fim == "2026-04-30"


def test_ac2_data_extenso_dia_de_mes_de_ano():
    db, ini, fim = _extrair_campos_vigencia(
        "Período de 1 de maio de 2025 até 30 de abril de 2026."
    )
    assert ini == "2025-05-01"
    assert fim == "2026-04-30"


def test_ac2_data_base_extenso_primeiro_de_mes():
    db, ini, fim = _extrair_campos_vigencia(
        "Data-base em 1º de outubro de 2025."
    )
    assert db == "2025-10-01"


def test_ac2_data_base_slash():
    db, ini, fim = _extrair_campos_vigencia(
        "Data-base: 01/05/2025."
    )
    assert db == "2025-05-01"


def test_ac2_data_sem_ano_retorna_none():
    """Datas sem ano não devem gerar ISO — campo permanece None."""
    db, ini, fim = _extrair_campos_vigencia(
        "Data-base em 1º de outubro."
    )
    assert db is None


def test_ac2_data_invalida_retorna_none():
    """Data impossível (30 de fevereiro) não deve gerar ISO."""
    db, ini, fim = _extrair_campos_vigencia(
        "Vigência de 30/02/2025 a 31/02/2026."
    )
    # Ambas as datas são inválidas; nenhum campo deve ser preenchido
    assert ini is None
    assert fim is None


def test_ac2_datas_normalizacao_acentos():
    """Nomes de mês com acento devem ser normalizados corretamente."""
    db, ini, fim = _extrair_campos_vigencia(
        "Vigência de 1 de março de 2025 a 28 de fevereiro de 2026."
    )
    assert ini == "2025-03-01"
    assert fim == "2026-02-28"


def test_ac2_campos_nao_identificados_sao_none():
    """Campos não encontrados devem ser None, nunca string vazia."""
    db, ini, fim = _extrair_campos_vigencia("Cláusula sem datas.")
    assert db is None
    assert ini is None
    assert fim is None


# ── AC3: status por tipo reajuste_salarial ────────────────────────────────────

def test_ac3_reajuste_extraido_com_sucesso():
    clausulas = [_clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%.")]
    r = extrair_reajustes(clausulas)[0]
    assert r.status_extracao_estruturada == "extraido_com_sucesso"
    assert r.percentual_reajuste is not None


def test_ac3_reajuste_dados_nao_identificados():
    clausulas = [_clausula(tipo="reajuste_salarial", trecho="Cláusula sem percentual.")]
    r = extrair_reajustes(clausulas)[0]
    assert r.status_extracao_estruturada == "dados_nao_identificados"
    assert r.percentual_reajuste is None


def test_ac3_reajuste_nao_avalia_campos_vigencia():
    """reajuste_salarial deve ser extraido_com_sucesso sem campos de vigência."""
    clausulas = [_clausula(tipo="reajuste_salarial", trecho="Reajuste de 8%.")]
    r = extrair_reajustes(clausulas)[0]
    assert r.status_extracao_estruturada == "extraido_com_sucesso"
    assert r.data_base is None
    assert r.vigencia_inicio is None
    assert r.vigencia_fim is None


# ── AC3: status por tipo vigencia_data_base ───────────────────────────────────

def test_ac3_vigencia_extraido_com_sucesso_range_completo():
    clausulas = [_clausula(
        tipo="vigencia_data_base",
        trecho="Vigência de 01/05/2025 a 30/04/2026.",
    )]
    r = extrair_reajustes(clausulas)[0]
    assert r.status_extracao_estruturada == "extraido_com_sucesso"
    assert r.vigencia_inicio == "2025-05-01"
    assert r.vigencia_fim == "2026-04-30"


def test_ac3_vigencia_extraido_com_sucesso_apenas_data_base():
    """Cláusula com apenas data-base deve ser extraido_com_sucesso."""
    clausulas = [_clausula(
        tipo="vigencia_data_base",
        trecho="A data-base da categoria é 1º de outubro de 2025.",
    )]
    r = extrair_reajustes(clausulas)[0]
    assert r.status_extracao_estruturada == "extraido_com_sucesso"
    assert r.data_base == "2025-10-01"


def test_ac3_vigencia_dados_nao_identificados():
    clausulas = [_clausula(
        tipo="vigencia_data_base",
        trecho="Vigência conforme acordo entre as partes.",
    )]
    r = extrair_reajustes(clausulas)[0]
    assert r.status_extracao_estruturada == "dados_nao_identificados"
    assert r.data_base is None
    assert r.vigencia_inicio is None
    assert r.vigencia_fim is None


def test_ac3_vigencia_parcialmente_extraido():
    """Quando texto indica range mas só uma data pode ser extraída."""
    # "vigência de" + uma data válida + conector + data inválida (30/02/2025)
    clausulas = [_clausula(
        tipo="vigencia_data_base",
        trecho="Vigência de 01/05/2025 a 30/02/2026.",
    )]
    r = extrair_reajustes(clausulas)[0]
    assert r.status_extracao_estruturada == "parcialmente_extraido"
    assert r.vigencia_inicio == "2025-05-01"
    assert r.vigencia_fim is None


def test_ac3_vigencia_nao_avalia_percentual():
    """vigencia_data_base não precisa de percentual para ser extraido_com_sucesso."""
    clausulas = [_clausula(
        tipo="vigencia_data_base",
        trecho="Vigência de 01/05/2025 a 30/04/2026.",
    )]
    r = extrair_reajustes(clausulas)[0]
    assert r.percentual_reajuste is None
    assert r.status_extracao_estruturada == "extraido_com_sucesso"


def test_ac3_erro_extracao_marca_status_correto(monkeypatch):
    """Exceção durante extração deve marcar status como erro_extracao."""
    from src.services import adjustment_extractor as extractor

    def _raise(*args, **kwargs):
        raise RuntimeError("Simulated error")

    monkeypatch.setattr(extractor, "_extrair_percentual", _raise)

    clausulas = [_clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%.")]
    r = extrair_reajustes(clausulas)[0]
    assert r.status_extracao_estruturada == "erro_extracao"
    assert r.percentual_reajuste is None


def test_ac3_erro_extracao_nao_interrompe_demais():
    """Erro em um registro não deve interromper os demais."""
    from src.services import adjustment_extractor as extractor

    original_extrair = extractor._extrair_percentual
    call_count = [0]

    def _fail_first(trecho):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("Simulated error")
        return original_extrair(trecho)

    clausulas = [
        _clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%."),
        _clausula(tipo="reajuste_salarial", trecho="Reajuste de 8%."),
    ]

    with patch.object(extractor, "_extrair_percentual", side_effect=_fail_first):
        resultados = extrair_reajustes(clausulas)

    assert len(resultados) == 2
    assert resultados[0].status_extracao_estruturada == "erro_extracao"
    assert resultados[1].status_extracao_estruturada == "extraido_com_sucesso"


# ── AC3: status válido sempre ─────────────────────────────────────────────────

def test_ac3_status_sempre_valor_valido():
    clausulas = [
        _clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%."),
        _clausula(tipo="reajuste_salarial", trecho="Sem percentual."),
        _clausula(tipo="vigencia_data_base", trecho="Vigência de 01/05/2025 a 30/04/2026."),
        _clausula(tipo="vigencia_data_base", trecho="Sem datas."),
    ]
    resultados = extrair_reajustes(clausulas)
    for r in resultados:
        assert r.status_extracao_estruturada in STATUS_EXTRACAO


# ── AC4: rastreabilidade e persistência atômica ───────────────────────────────

def test_ac4_campos_obrigatorios_presentes():
    clausulas = [_clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%.")]
    r = extrair_reajustes(clausulas)[0]

    campos = [
        "caminho", "nome_arquivo", "uf", "sindicato", "tipo_documento",
        "ano_referencia", "origem_texto", "tipo_clausula", "trecho_original",
        "percentual_reajuste", "data_base", "vigencia_inicio", "vigencia_fim",
        "status_extracao_estruturada", "metodo_extracao", "data_hora_processamento",
    ]
    for campo in campos:
        assert hasattr(r, campo), f"Campo ausente: {campo}"


def test_ac4_campos_nao_encontrados_sao_none_nao_string_vazia():
    clausulas = [_clausula(tipo="reajuste_salarial", trecho="Cláusula sem percentual.")]
    r = extrair_reajustes(clausulas)[0]
    # Campos não extraídos devem ser None
    assert r.percentual_reajuste is None
    assert r.data_base is None
    assert r.vigencia_inicio is None
    assert r.vigencia_fim is None


def test_ac4_trecho_original_preservado():
    trecho = "Reajuste de 5% conforme negociação."
    clausulas = [_clausula(tipo="reajuste_salarial", trecho=trecho)]
    r = extrair_reajustes(clausulas)[0]
    assert r.trecho_original == trecho


def test_ac4_rastreabilidade_campos_origem(tmp_path):
    clausulas = [_clausula(
        tipo="reajuste_salarial",
        trecho="Reajuste de 5%.",
        caminho="CCT/MG/Sind2/b.pdf",
        uf="MG",
        sindicato="Sind2",
        tipo_documento="Termo Aditivo",
        ano_referencia="2024-2025",
    )]
    reajustes = extrair_reajustes(clausulas)
    output = tmp_path / "reajustes.json"
    salvar_reajustes(output, reajustes)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    r = dados["reajustes"][0]
    assert r["caminho"] == "CCT/MG/Sind2/b.pdf"
    assert r["uf"] == "MG"
    assert r["sindicato"] == "Sind2"
    assert r["tipo_documento"] == "Termo Aditivo"
    assert r["ano_referencia"] == "2024-2025"


def test_ac4_escrita_atomica(tmp_path):
    """Arquivo de saída deve ser criado via tempfile + os.replace."""
    reajustes = extrair_reajustes([_clausula(tipo="reajuste_salarial", trecho="5%.")])
    output = tmp_path / "data" / "reajustes_extraidos.json"
    salvar_reajustes(output, reajustes)

    assert output.exists()
    # Não deve haver arquivos .tmp residuais
    tmp_files = list(output.parent.glob("*.tmp"))
    assert tmp_files == []


def test_ac4_json_estrutura_versao_e_data_geracao(tmp_path):
    reajustes = extrair_reajustes([_clausula(tipo="reajuste_salarial", trecho="5%.")])
    output = tmp_path / "r.json"
    salvar_reajustes(output, reajustes)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert "versao" in dados
    assert "data_geracao" in dados
    assert "reajustes" in dados
    assert isinstance(dados["reajustes"], list)


def test_ac4_roundtrip_salvar_carregar(tmp_path):
    clausulas = [
        _clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%."),
        _clausula(tipo="vigencia_data_base", trecho="Vigência de 01/05/2025 a 30/04/2026."),
    ]
    reajustes = extrair_reajustes(clausulas)
    output = tmp_path / "r.json"
    salvar_reajustes(output, reajustes)

    carregados = carregar_reajustes(output)
    assert len(carregados) == 2
    assert carregados[0].tipo_clausula == "reajuste_salarial"
    assert carregados[1].tipo_clausula == "vigencia_data_base"


def test_ac4_carregar_arquivo_inexistente_retorna_lista_vazia(tmp_path):
    resultado = carregar_reajustes(tmp_path / "nao_existe.json")
    assert resultado == []


def test_ac4_campos_null_persistidos_como_null_no_json(tmp_path):
    clausulas = [_clausula(tipo="reajuste_salarial", trecho="Sem percentual.")]
    reajustes = extrair_reajustes(clausulas)
    output = tmp_path / "r.json"
    salvar_reajustes(output, reajustes)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    r = dados["reajustes"][0]
    assert r["percentual_reajuste"] is None
    assert r["data_base"] is None
    assert r["vigencia_inicio"] is None
    assert r["vigencia_fim"] is None


# ── AC5: relatório de totais ──────────────────────────────────────────────────

def test_ac5_relatorio_soma_status_igual_total_escopo(capsys):
    clausulas = [
        _clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%."),
        _clausula(tipo="reajuste_salarial", trecho="Sem percentual."),
        _clausula(tipo="vigencia_data_base", trecho="Vigência de 01/05/2025 a 30/04/2026."),
        _clausula(tipo="vigencia_data_base", trecho="Sem datas."),
        _clausula(tipo="piso_salarial", trecho="Piso."),  # ignorada
    ]
    reajustes = extrair_reajustes(clausulas)

    total_avaliadas = len(clausulas)
    total_escopo = sum(1 for c in clausulas if c.tipo_clausula in _TIPOS_ESCOPO)
    total_ignoradas = total_avaliadas - total_escopo

    imprimir_relatorio_reajustes(total_avaliadas, total_escopo, total_ignoradas, reajustes)

    captured = capsys.readouterr().out
    assert "Total de cláusulas avaliadas" in captured
    assert "Cláusulas no escopo" in captured
    assert "Ignoradas por categoria" in captured
    assert "Extraído com sucesso" in captured
    assert "Parcialmente extraído" in captured
    assert "Dados não identificados" in captured
    assert "Erro na extração" in captured


def test_ac5_contadores_de_status_somam_total_escopo(capsys):
    clausulas = [
        _clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%."),
        _clausula(tipo="reajuste_salarial", trecho="Sem percentual."),
        _clausula(tipo="vigencia_data_base", trecho="Vigência de 01/05/2025 a 30/04/2026."),
        _clausula(tipo="beneficios", trecho="Benefícios."),  # ignorada
    ]
    reajustes = extrair_reajustes(clausulas)
    total_escopo = sum(1 for c in clausulas if c.tipo_clausula in _TIPOS_ESCOPO)

    assert len(reajustes) == total_escopo

    extraido = sum(1 for r in reajustes if r.status_extracao_estruturada == "extraido_com_sucesso")
    parcial = sum(1 for r in reajustes if r.status_extracao_estruturada == "parcialmente_extraido")
    nao_id = sum(1 for r in reajustes if r.status_extracao_estruturada == "dados_nao_identificados")
    erro = sum(1 for r in reajustes if r.status_extracao_estruturada == "erro_extracao")

    assert extraido + parcial + nao_id + erro == total_escopo


# ── CLI integration: arquivo de entrada ausente ───────────────────────────────

def test_cli_arquivo_ausente_retorna_erro(tmp_path):
    from src.cli import main

    resultado = main([
        "extract-adjustments",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(tmp_path / "out.json"),
    ])
    assert resultado == 1


def test_cli_arquivo_ausente_mensagem_orienta_usuario(tmp_path, capsys):
    from src.cli import main

    main([
        "extract-adjustments",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(tmp_path / "out.json"),
    ])

    captured = capsys.readouterr()
    assert "identify-clauses" in captured.err


def test_cli_processa_clausulas_e_gera_saida(tmp_path):
    """Integração: CLI lê clausulas_candidatas.json e gera reajustes_extraidos.json."""
    from src.services.clause_store import salvar_clausulas
    from src.cli import main

    clausulas = [
        _clausula(tipo="reajuste_salarial", trecho="Reajuste de 5%."),
        _clausula(tipo="vigencia_data_base", trecho="Vigência de 01/05/2025 a 30/04/2026."),
    ]
    input_path = tmp_path / "clausulas.json"
    output_path = tmp_path / "reajustes.json"
    salvar_clausulas(input_path, clausulas)

    resultado = main([
        "extract-adjustments",
        "--input", str(input_path),
        "--output", str(output_path),
    ])

    assert resultado == 0
    assert output_path.exists()

    with output_path.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert len(dados["reajustes"]) == 2
