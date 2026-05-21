"""Testes para o comando export-params e módulos de exportação de parâmetros sindicais.

Cobre os critérios de aceitação da US-PRJ-15:
  AC1 — campos corretos para registros válidos (um aprovado por chave)
  AC2 — filtragem exclusiva de aprovados; outros status ignorados silenciosamente
  AC3 — registro consolidado de conflito (múltiplos aprovados por chave)
  AC4 — campo data_geracao no arquivo + relatório com totais e caminho absoluto
  AC5 — subcomando CLI com --input opcional + escrita atômica
"""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from src.models.reajuste_aprovado import ReajusteAprovado
from src.services.sindical_params_exporter import (
    exportar_parametros,
    salvar_parametros,
    STATUS_VALIDO,
    STATUS_CONFLITO,
    OBS_CONFLITO,
)
from src.reports.sindical_params import imprimir_relatorio_exportacao

_TIMESTAMP = "2025-05-20T12:00:00+00:00"


# ── helpers ───────────────────────────────────────────────────────────────────

def _aprovado(
    uf: str = "SP",
    sindicato: str = "Sindicato Teste",
    ano: str = "2025",
    percentual_final: str = "5%",
    data_base: str = "2025-01-01",
    vigencia_inicio: str = "2025-01-01",
    vigencia_fim: str = "2025-12-31",
    nome_arquivo: str = "cct.pdf",
    status: str = "aprovado",
    id_registro: str = None,
) -> ReajusteAprovado:
    return ReajusteAprovado(
        id_registro=id_registro or str(uuid.uuid4()),
        caminho=f"CCT/{uf}/{nome_arquivo}",
        nome_arquivo=nome_arquivo,
        uf=uf,
        sindicato=sindicato,
        tipo_documento="CCT",
        ano_referencia=ano,
        tipo_clausula="reajuste_salarial",
        trecho_original="Reajuste de 5%.",
        percentual_reajuste_original=percentual_final,
        percentual_reajuste_final=percentual_final,
        data_base_original=data_base,
        data_base_final=data_base,
        vigencia_inicio_original=vigencia_inicio,
        vigencia_inicio_final=vigencia_inicio,
        vigencia_fim_original=vigencia_fim,
        vigencia_fim_final=vigencia_fim,
        status_validacao=status,
        responsavel_validacao="ana.silva",
        data_hora_validacao=_TIMESTAMP,
        observacao_validacao=None,
        data_hora_geracao=_TIMESTAMP,
    )


# ── AC1: campos corretos para registros válidos ───────────────────────────────

def test_ac1_registro_valido_todos_os_campos_presentes():
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    assert len(parametros) == 1
    p = parametros[0]
    campos_obrigatorios = {
        "chave_parametro", "uf", "sindicato", "ano_referencia",
        "percentual_reajuste", "data_base", "vigencia_inicio", "vigencia_fim",
        "fonte_documento", "status_aprovacao", "data_ultima_atualizacao",
        "status_parametro", "conflito", "id_registro_reajuste",
        "ids_registros_conflitantes", "observacao",
    }
    assert campos_obrigatorios.issubset(set(p.keys()))


def test_ac1_registro_valido_status_parametro():
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    assert parametros[0]["status_parametro"] == STATUS_VALIDO


def test_ac1_registro_valido_conflito_false():
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    assert parametros[0]["conflito"] is False


def test_ac1_registro_valido_ids_conflitantes_vazio():
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    assert parametros[0]["ids_registros_conflitantes"] == []


def test_ac1_registro_valido_observacao_null():
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    assert parametros[0]["observacao"] is None


def test_ac1_mapeamento_campos_final():
    r = _aprovado(percentual_final="6%", data_base="2025-03-01",
                  vigencia_inicio="2025-03-01", vigencia_fim="2026-02-28",
                  nome_arquivo="arquivo.pdf")
    parametros, _ = exportar_parametros([r])
    p = parametros[0]
    assert p["percentual_reajuste"] == "6%"
    assert p["data_base"] == "2025-03-01"
    assert p["vigencia_inicio"] == "2025-03-01"
    assert p["vigencia_fim"] == "2026-02-28"
    assert p["fonte_documento"] == "arquivo.pdf"     # ← nome_arquivo
    assert p["data_ultima_atualizacao"] == _TIMESTAMP  # ← data_hora_geracao
    assert p["status_aprovacao"] == "aprovado"


def test_ac1_id_registro_reajuste_mapeado():
    r = _aprovado(id_registro="id-abc-123")
    parametros, _ = exportar_parametros([r])
    assert parametros[0]["id_registro_reajuste"] == "id-abc-123"


def test_ac1_chave_parametro_normalizada():
    r = _aprovado(uf="SP", sindicato="Sindicato Têxtil", ano="2025")
    parametros, _ = exportar_parametros([r])
    chave = parametros[0]["chave_parametro"]
    # Chave deve ser normalizada (sem acentos, minúsculas)
    assert "ê" not in chave
    assert chave == chave.lower()
    assert "|" in chave


def test_ac1_valores_armazenados_sao_originais_nao_normalizados():
    r = _aprovado(uf="SP", sindicato="Sindicato Têxtil", ano="2025-2026")
    parametros, _ = exportar_parametros([r])
    p = parametros[0]
    assert p["uf"] == "SP"
    assert p["sindicato"] == "Sindicato Têxtil"
    assert p["ano_referencia"] == "2025-2026"


# ── AC2: filtragem de status ──────────────────────────────────────────────────

def test_ac2_somente_aprovados_sao_processados():
    registros = [
        _aprovado(status="aprovado"),
        _aprovado(status="rejeitado"),
        _aprovado(status="pendente"),
        _aprovado(status="erro"),
    ]
    parametros, _ = exportar_parametros(registros)
    assert len(parametros) == 1


@pytest.mark.parametrize("status", ["rejeitado", "pendente", "erro", "pendente_revisao"])
def test_ac2_status_nao_aprovado_silenciosamente_excluido(status):
    r = _aprovado(status=status)
    parametros, _ = exportar_parametros([r])
    assert parametros == []


def test_ac2_lista_vazia_retorna_sem_erro():
    parametros, total_conflitos = exportar_parametros([])
    assert parametros == []
    assert total_conflitos == 0


def test_ac2_apenas_nao_aprovados_retorna_lista_vazia():
    registros = [_aprovado(status="rejeitado"), _aprovado(status="pendente")]
    parametros, _ = exportar_parametros(registros)
    assert parametros == []


# ── AC3: registro consolidado de conflito ────────────────────────────────────

def test_ac3_conflito_quando_multiplos_aprovados_mesma_chave():
    r1 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-1")
    r2 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-2")
    parametros, total_conflitos = exportar_parametros([r1, r2])
    assert len(parametros) == 1
    assert total_conflitos == 1
    assert parametros[0]["status_parametro"] == STATUS_CONFLITO


def test_ac3_conflito_campos_reajuste_nulos():
    r1 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-1")
    r2 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-2")
    parametros, _ = exportar_parametros([r1, r2])
    p = parametros[0]
    assert p["percentual_reajuste"] is None
    assert p["data_base"] is None
    assert p["vigencia_inicio"] is None
    assert p["vigencia_fim"] is None
    assert p["fonte_documento"] is None
    assert p["data_ultima_atualizacao"] is None
    assert p["status_aprovacao"] is None
    assert p["id_registro_reajuste"] is None


def test_ac3_conflito_true():
    r1 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-1")
    r2 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-2")
    parametros, _ = exportar_parametros([r1, r2])
    assert parametros[0]["conflito"] is True


def test_ac3_ids_registros_conflitantes_preenchido():
    r1 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-1")
    r2 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-2")
    r3 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-3")
    parametros, _ = exportar_parametros([r1, r2, r3])
    ids = parametros[0]["ids_registros_conflitantes"]
    assert sorted(ids) == ["id-1", "id-2", "id-3"]


def test_ac3_observacao_conflito():
    r1 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-1")
    r2 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-2")
    parametros, _ = exportar_parametros([r1, r2])
    assert parametros[0]["observacao"] == OBS_CONFLITO


def test_ac3_chaves_diferentes_sem_conflito():
    r1 = _aprovado(uf="SP", sindicato="Sind A", ano="2025")
    r2 = _aprovado(uf="RJ", sindicato="Sind B", ano="2025")
    parametros, total_conflitos = exportar_parametros([r1, r2])
    assert len(parametros) == 2
    assert total_conflitos == 0
    statuses = {p["status_parametro"] for p in parametros}
    assert statuses == {STATUS_VALIDO}


def test_ac3_chave_normalizada_detecta_conflito_com_acentuacao():
    """Registros com acento vs sem acento na mesma chave devem ser detectados como conflito."""
    r1 = _aprovado(uf="SP", sindicato="Sindicato Têxtil", ano="2025", id_registro="id-1")
    r2 = _aprovado(uf="SP", sindicato="Sindicato Textil", ano="2025", id_registro="id-2")
    parametros, total_conflitos = exportar_parametros([r1, r2])
    assert len(parametros) == 1
    assert total_conflitos == 1
    assert parametros[0]["status_parametro"] == STATUS_CONFLITO


def test_ac3_nenhuma_heuristica_de_desempate():
    """Quando há conflito, nenhum registro individual é escolhido como 'valido'."""
    r1 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-1", percentual_final="5%")
    r2 = _aprovado(uf="SP", sindicato="Sind", ano="2025", id_registro="id-2", percentual_final="6%")
    parametros, _ = exportar_parametros([r1, r2])
    assert len(parametros) == 1
    assert parametros[0]["percentual_reajuste"] is None


# ── AC4: data_geracao + relatório ─────────────────────────────────────────────

def test_ac4_arquivo_contem_data_geracao(tmp_path):
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    output = tmp_path / "params.json"
    salvar_parametros(output, parametros, _TIMESTAMP)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert "data_geracao" in dados
    assert dados["data_geracao"] == _TIMESTAMP


def test_ac4_arquivo_contem_campo_parametros(tmp_path):
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    output = tmp_path / "params.json"
    salvar_parametros(output, parametros, _TIMESTAMP)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert "parametros" in dados
    assert isinstance(dados["parametros"], list)


def test_ac4_relatorio_exibe_total_exportados(capsys):
    imprimir_relatorio_exportacao(
        total_exportados=5,
        total_conflitos=1,
        output_path_absoluto="/abs/path/base.json",
    )
    captured = capsys.readouterr()
    assert "5" in captured.out


def test_ac4_relatorio_exibe_total_conflitos(capsys):
    imprimir_relatorio_exportacao(3, 2, "/abs/path/base.json")
    captured = capsys.readouterr()
    assert "2" in captured.out


def test_ac4_relatorio_exibe_caminho_absoluto(capsys):
    imprimir_relatorio_exportacao(3, 0, "/abs/path/base_parametros_sindicais.json")
    captured = capsys.readouterr()
    assert "/abs/path/base_parametros_sindicais.json" in captured.out


# ── AC5: CLI + escrita atômica ────────────────────────────────────────────────

def test_ac5_subcomando_registrado():
    from src.cli import build_parser
    parser = build_parser()
    # Deve parsear sem erro
    args = parser.parse_args(["export-params"])
    assert hasattr(args, "func")


def test_ac5_argumento_input_opcional():
    from src.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["export-params"])
    assert args.input is not None  # usa padrão DEFAULT_APPROVED_OUTPUT


def test_ac5_argumento_input_aceita_sobrescrita():
    from src.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["export-params", "--input", "/custom/path.json"])
    assert args.input == "/custom/path.json"


def test_ac5_escrita_atomica_sem_residuo(tmp_path):
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    output = tmp_path / "params.json"
    salvar_parametros(output, parametros, _TIMESTAMP)

    arquivos = list(tmp_path.iterdir())
    assert output in arquivos
    assert [f for f in arquivos if f.suffix == ".tmp"] == []


def test_ac5_escrita_atomica_nao_corrompe_arquivo_existente(tmp_path):
    output = tmp_path / "params.json"
    conteudo_original = '{"parametros": []}'
    output.write_text(conteudo_original, encoding="utf-8")

    r = _aprovado()
    parametros, _ = exportar_parametros([r])

    with patch("os.replace", side_effect=OSError("falha simulada")):
        with pytest.raises(OSError):
            salvar_parametros(output, parametros, _TIMESTAMP)

    assert output.read_text(encoding="utf-8") == conteudo_original


def test_ac5_arquivo_temporario_removido_em_caso_de_falha(tmp_path):
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    output = tmp_path / "params.json"

    with patch("os.replace", side_effect=OSError("falha simulada")):
        with pytest.raises(OSError):
            salvar_parametros(output, parametros, _TIMESTAMP)

    tmp_files = [f for f in tmp_path.iterdir() if f.suffix == ".tmp"]
    assert tmp_files == []


def test_ac5_arquivo_saida_e_json_valido(tmp_path):
    r = _aprovado()
    parametros, _ = exportar_parametros([r])
    output = tmp_path / "params.json"
    salvar_parametros(output, parametros, _TIMESTAMP)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert isinstance(dados, dict)
    assert "parametros" in dados


def test_ac5_cli_arquivo_ausente_retorna_1(tmp_path):
    from src.cli import main
    codigo = main([
        "export-params",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(tmp_path / "out.json"),
    ])
    assert codigo == 1


def test_ac5_cli_arquivo_ausente_nao_cria_saida(tmp_path):
    from src.cli import main
    output = tmp_path / "out.json"
    main([
        "export-params",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(output),
    ])
    assert not output.exists()


def test_ac5_cli_fluxo_completo(tmp_path):
    from src.cli import main
    from src.services.approved_store import salvar_aprovados

    registros = [
        _aprovado(uf="SP", sindicato="Sind A", ano="2025", id_registro="id-1"),
        _aprovado(uf="RJ", sindicato="Sind B", ano="2025", id_registro="id-2"),
        _aprovado(uf="SP", sindicato="Sind A", ano="2025", id_registro="id-3"),  # conflito
        _aprovado(uf="MG", sindicato="Sind C", ano="2025", status="rejeitado"),  # ignorado
    ]

    input_file = tmp_path / "reajustes_aprovados.json"
    output_file = tmp_path / "base_parametros_sindicais.json"
    salvar_aprovados(input_file, registros)

    codigo = main([
        "export-params",
        "--input", str(input_file),
        "--output", str(output_file),
    ])

    assert codigo == 0
    assert output_file.exists()

    with output_file.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert "data_geracao" in dados
    assert len(dados["parametros"]) == 2  # SP/Sind A (conflito) + RJ/Sind B (valido)

    statuses = {p["status_parametro"] for p in dados["parametros"]}
    assert STATUS_VALIDO in statuses
    assert STATUS_CONFLITO in statuses


def test_ac5_cli_retorna_0_com_aprovados(tmp_path):
    from src.cli import main
    from src.services.approved_store import salvar_aprovados

    input_file = tmp_path / "aprovados.json"
    salvar_aprovados(input_file, [_aprovado()])

    codigo = main([
        "export-params",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.json"),
    ])
    assert codigo == 0


def test_ac5_cli_relatorio_exibido(tmp_path, capsys):
    from src.cli import main
    from src.services.approved_store import salvar_aprovados

    registros = [
        _aprovado(uf="SP", sindicato="Sind A", ano="2025", id_registro="id-1"),
        _aprovado(uf="SP", sindicato="Sind A", ano="2025", id_registro="id-2"),  # conflito
    ]
    input_file = tmp_path / "aprovados.json"
    salvar_aprovados(input_file, registros)

    main([
        "export-params",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.json"),
    ])

    captured = capsys.readouterr()
    assert "1" in captured.out  # 1 registro exportado (conflito)
    assert str(tmp_path / "out.json") in captured.out  # caminho absoluto
