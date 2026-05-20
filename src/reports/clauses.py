"""Relatório de cobertura da identificação de cláusulas candidatas.

Exibe totais de documentos avaliados, analisados, ignorados e cláusulas
encontradas por tipo de tema — conforme AC5.
"""

from typing import List

from src.models.clausula_candidata import ClausulaCandidata, TIPOS_CLAUSULA

_TIPOS_ORDENADOS = [
    "reajuste_salarial",
    "piso_salarial",
    "vale_refeicao",
    "vale_alimentacao",
    "beneficios",
    "adicionais",
    "plr",
    "auxilio_home_office",
    "vigencia_data_base",
    "outros_remuneracao",
]

_LABELS = {
    "reajuste_salarial":   "Reajuste salarial       ",
    "piso_salarial":       "Piso salarial           ",
    "vale_refeicao":       "Vale refeição           ",
    "vale_alimentacao":    "Vale alimentação        ",
    "beneficios":          "Benefícios              ",
    "adicionais":          "Adicionais              ",
    "plr":                 "PLR                     ",
    "auxilio_home_office": "Auxílio home office     ",
    "vigencia_data_base":  "Vigência / data-base    ",
    "outros_remuneracao":  "Outros remuneração      ",
}


def imprimir_relatorio_clausulas(
    total_avaliados: int,
    total_analisados: int,
    total_ignorados: int,
    clausulas: List[ClausulaCandidata],
) -> None:
    """Imprime relatório de cobertura da identificação de cláusulas (AC5)."""
    total_clausulas = len(clausulas)

    contadores: dict = {t: 0 for t in _TIPOS_ORDENADOS}
    for c in clausulas:
        if c.tipo_clausula in contadores:
            contadores[c.tipo_clausula] += 1

    print("\n=== Relatório de Identificação de Cláusulas ===")
    print(f"  Total de documentos avaliados  : {total_avaliados}")
    print(f"  Documentos analisados (com texto): {total_analisados}")
    print(f"  Documentos ignorados (sem texto) : {total_ignorados}")
    print(f"  Total de cláusulas candidatas  : {total_clausulas}")
    print()
    print("  Cláusulas por tipo:")
    for tipo in _TIPOS_ORDENADOS:
        label = _LABELS.get(tipo, tipo)
        print(f"    {label}: {contadores[tipo]}")
    print()
