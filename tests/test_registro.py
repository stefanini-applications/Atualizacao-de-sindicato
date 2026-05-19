"""Testes das regras de negócio para o registro de documentos sindicais.

Cobre os critérios de aceitação da US-PRJ-2:
  AC1 — campos esperados de cadastro não bloqueiam salvamento
  AC2 — campos críticos ausentes invalidam para extração
  AC3 — tipos e status restritos aos valores aceitos
  AC4 — reconhecimento automático de UF e sindicato via scanner
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.documento import (
    DocumentoSindical,
    TIPOS_VALIDOS,
    STATUS_VALIDOS,
    UFS_VALIDAS,
)
from src.services.validator import (
    valido_para_extracao,
    campos_incompletos,
    campos_criticos_ausentes_ou_invalidos,
)
from src.services.scanner import _inferir_tipo, _inferir_anos, _inferir_sindicato_do_nome


def _doc(**kwargs) -> DocumentoSindical:
    defaults = dict(
        id="test-id",
        nome_arquivo="CCT_2025-2026_Sindpd-SP.pdf",
        caminho="CCT/SP/Sindpd/CCT_2025-2026_Sindpd-SP.pdf",
        uf="SP",
        sindicato="Sindpd",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        status="pendente de validação",
        data_inclusao="2025-01-01T00:00:00+00:00",
        responsavel="Teste",
        vigencia_inicial="2025",
        vigencia_final="2026",
    )
    defaults.update(kwargs)
    return DocumentoSindical(**defaults)


# ── AC1: salvamento não bloqueado ─────────────────────────────────────────────

def test_doc_completo_valido():
    """Documento com todos os campos deve ser válido para extração."""
    doc = _doc()
    assert valido_para_extracao(doc)
    assert campos_incompletos(doc) == []


def test_doc_sem_ano_referencia_valido_porem_incompleto():
    """Sem ano_referencia: válido para extração, mas sinalizado como incompleto."""
    doc = _doc(ano_referencia=None)
    assert valido_para_extracao(doc), "ausência de ano_referencia não deve bloquear extração"
    assert "ano_referencia" in campos_incompletos(doc)


def test_doc_sem_responsavel_valido_porem_incompleto():
    """Sem responsavel: válido para extração, mas sinalizado como incompleto."""
    doc = _doc(responsavel=None)
    assert valido_para_extracao(doc)
    assert "responsavel" in campos_incompletos(doc)


def test_doc_sem_data_inclusao_incompleto():
    """Sem data_inclusao: incompleto mas não invalida extração."""
    doc = _doc(data_inclusao=None)
    assert valido_para_extracao(doc)
    assert "data_inclusao" in campos_incompletos(doc)


# ── AC2: campos críticos invalidam para extração ──────────────────────────────

def test_doc_sem_uf_invalido():
    """Sem UF: inválido para extração."""
    doc = _doc(uf=None)
    assert not valido_para_extracao(doc)
    problemas = campos_criticos_ausentes_ou_invalidos(doc)
    assert any("uf" in p for p in problemas)


def test_doc_sem_sindicato_invalido():
    """Sem sindicato: inválido para extração."""
    doc = _doc(sindicato=None)
    assert not valido_para_extracao(doc)
    problemas = campos_criticos_ausentes_ou_invalidos(doc)
    assert any("sindicato" in p for p in problemas)


def test_doc_sem_tipo_documento_invalido():
    """Sem tipo_documento: inválido para extração."""
    doc = _doc(tipo_documento=None)
    assert not valido_para_extracao(doc)
    problemas = campos_criticos_ausentes_ou_invalidos(doc)
    assert any("tipo_documento" in p for p in problemas)


def test_doc_tipo_invalido_invalido_extracao():
    """tipo_documento fora dos valores aceitos: inválido para extração."""
    doc = _doc(tipo_documento="Circular")
    assert not valido_para_extracao(doc)


def test_doc_uf_invalida_invalido_extracao():
    """UF fora dos 27 estados: inválido para extração."""
    doc = _doc(uf="XX")
    assert not valido_para_extracao(doc)
    problemas = campos_criticos_ausentes_ou_invalidos(doc)
    assert any("uf" in p for p in problemas)


def test_ausencia_todos_criticos_invalido():
    """Ausência dos 3 campos críticos: inválido para extração."""
    doc = _doc(uf=None, sindicato=None, tipo_documento=None)
    assert not valido_para_extracao(doc)
    assert len(campos_criticos_ausentes_ou_invalidos(doc)) == 3


# ── AC3: tipos e status restritos ────────────────────────────────────────────

def test_tipos_validos_definidos():
    assert "CCT" in TIPOS_VALIDOS
    assert "termo aditivo" in TIPOS_VALIDOS
    assert "acordo coletivo" in TIPOS_VALIDOS
    assert "outro documento sindical" in TIPOS_VALIDOS
    assert len(TIPOS_VALIDOS) == 4


def test_status_validos_definidos():
    assert "pendente de validação" in STATUS_VALIDOS
    assert "vigente" in STATUS_VALIDOS
    assert "substituído" in STATUS_VALIDOS
    assert "vencido" in STATUS_VALIDOS
    assert "erro de classificação" in STATUS_VALIDOS
    assert len(STATUS_VALIDOS) == 5


def test_ufs_validas_27_estados():
    assert len(UFS_VALIDAS) == 27
    assert "SP" in UFS_VALIDAS
    assert "AP" in UFS_VALIDAS


# ── AC4: inferência automática via scanner ────────────────────────────────────

def test_inferir_tipo_cct():
    assert _inferir_tipo("CCT_2025-2026_Sindpd-SP (homologado).pdf") == "CCT"
    assert _inferir_tipo("CCT SEAC 2025.pdf") == "CCT"
    assert _inferir_tipo("CCT 2025_SINTTEL MG.pdf") == "CCT"


def test_inferir_tipo_aditivo():
    assert _inferir_tipo("Termo aditivo SEAC AC - 2026.pdf") == "termo aditivo"
    assert _inferir_tipo("ADITIVO CCT 2025-2026_SINDPD-MT (1).pdf") == "termo aditivo"
    assert _inferir_tipo("Aditivo 2024 - CCT SINTELL AL.pdf") == "termo aditivo"


def test_inferir_tipo_acordo_coletivo():
    assert _inferir_tipo("ACORDO COLETIVO SINDICAL – FENATI MG.pdf") == "acordo coletivo"
    assert _inferir_tipo("ACT_2025_Sindpd-AM (homologado).pdf") == "acordo coletivo"
    assert _inferir_tipo("ACT 2025-2026_SINDTOB.pdf") == "acordo coletivo"


def test_inferir_tipo_outro():
    assert _inferir_tipo("Circular Reajuste Salarial 2025.pdf") == "outro documento sindical"
    assert _inferir_tipo("SINDADOS - BA - 2025-2027.pdf") == "outro documento sindical"


def test_inferir_anos_range():
    ano, ini, fim = _inferir_anos("CCT_2025-2026_Sindpd-SP")
    assert ano == "2025-2026"
    assert ini == "2025"
    assert fim == "2026"


def test_inferir_anos_underscore():
    ano, ini, fim = _inferir_anos("CCT_2024_2025_Sindpd-SP (homologado)")
    assert ano == "2024-2025"
    assert ini == "2024"
    assert fim == "2025"


def test_inferir_anos_unico():
    ano, ini, fim = _inferir_anos("CCT 2025_SINTTEL MG")
    assert ano == "2025"
    assert ini == "2025"
    assert fim is None


def test_inferir_anos_sem_ano():
    ano, ini, fim = _inferir_anos("SESCON PB (2)")
    assert ano is None
    assert ini is None
    assert fim is None


def test_inferir_sindicato_do_nome():
    resultado = _inferir_sindicato_do_nome("CCT_2025-2026_Sindpd-AP")
    assert resultado is not None
    assert "Sindpd" in resultado or "sindpd" in resultado.lower()


if __name__ == "__main__":
    import traceback

    tests = [name for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    failed = 0
    for name in tests:
        try:
            globals()[name]()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
            traceback.print_exc()
            failed += 1
        except Exception as e:
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passou(ram), {failed} falhou(aram)")
    sys.exit(0 if failed == 0 else 1)
