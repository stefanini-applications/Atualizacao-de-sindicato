"""Testes da extração de texto de PDFs sindicais.

Cobre os critérios de aceitação da US-PRJ-3:
  AC1 — seleção de documentos elegíveis
  AC2 — armazenamento rastreável do texto extraído
  AC3 — exatamente um dos cinco status por documento
  AC4 — PDFs sem texto tratados sem interrupção
  AC5 — relatório consolidado com soma == total
"""

import io
import sys
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.documento import DocumentoSindical
from src.models.texto_extraido import TextoExtraido, STATUS_EXTRACAO
from src.services.extractor import extrair_texto_pdf, processar_extracao
from src.services.extraction_store import salvar_textos, carregar_textos
from src.reports.extraction import imprimir_relatorio_extracao


# ── helpers ───────────────────────────────────────────────────────────────────

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


def _texto_extraido(**kwargs) -> TextoExtraido:
    defaults = dict(
        caminho="CCT/SP/Sindpd/CCT_2025-2026_Sindpd-SP.pdf",
        nome_arquivo="CCT_2025-2026_Sindpd-SP.pdf",
        uf="SP",
        sindicato="Sindpd",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        texto="Texto de exemplo.",
        num_caracteres=17,
        status="extraido_com_sucesso",
        data_processamento="2025-01-01T00:00:00+00:00",
    )
    defaults.update(kwargs)
    return TextoExtraido(**defaults)


# ── AC1: seleção de elegíveis ─────────────────────────────────────────────────

def test_doc_invalido_recebe_status_nao_elegivel():
    """Documento sem UF deve receber status nao_elegivel_para_extracao."""
    doc = _doc(id="d1", caminho="CCT/??/Sindpd/a.pdf", uf=None)
    registro = {doc.caminho: doc}

    with tempfile.TemporaryDirectory() as tmpdir:
        raiz = Path(tmpdir)
        resultados = processar_extracao(registro, raiz)

    assert len(resultados) == 1
    assert resultados[0].status == "nao_elegivel_para_extracao"
    assert resultados[0].texto == ""
    assert resultados[0].num_caracteres == 0


def test_doc_invalido_nao_interrompe_elegivel():
    """Documento inelegível não deve bloquear os demais."""
    doc_invalido = _doc(id="d1", caminho="CCT/??/Sindpd/a.pdf", uf=None, nome_arquivo="a.pdf")
    doc_valido = _doc(id="d2", caminho="CCT/SP/Sindpd/b.pdf", nome_arquivo="b.pdf")
    registro = {
        doc_invalido.caminho: doc_invalido,
        doc_valido.caminho: doc_valido,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        raiz = Path(tmpdir)
        # b.pdf não existe, mas deve receber documento_nao_encontrado, não causar exceção
        resultados = processar_extracao(registro, raiz)

    statuses = {r.caminho: r.status for r in resultados}
    assert statuses[doc_invalido.caminho] == "nao_elegivel_para_extracao"
    assert statuses[doc_valido.caminho] == "documento_nao_encontrado"


# ── AC2: armazenamento rastreável ─────────────────────────────────────────────

def test_extracao_bem_sucedida_armazena_campos_rastreabilidade():
    """Extração com sucesso deve preencher todos os campos de rastreabilidade."""
    doc = _doc()
    registro = {doc.caminho: doc}

    with tempfile.TemporaryDirectory() as tmpdir:
        raiz = Path(tmpdir)
        pdf_path = raiz / doc.caminho
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        # Mock pypdf para simular PDF com texto
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Cláusula 1: Salário mínimo."
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("src.services.extractor.pypdf") as mock_pypdf:
            mock_pypdf.PdfReader.return_value = mock_reader
            # Criar arquivo vazio para que exists() retorne True
            pdf_path.touch()
            resultados = processar_extracao(registro, raiz)

    assert len(resultados) == 1
    r = resultados[0]
    assert r.caminho == doc.caminho
    assert r.nome_arquivo == doc.nome_arquivo
    assert r.uf == "SP"
    assert r.sindicato == "Sindpd"
    assert r.tipo_documento == "CCT"
    assert r.ano_referencia == "2025-2026"
    assert r.status == "extraido_com_sucesso"
    assert r.num_caracteres > 0
    assert r.num_caracteres == len(r.texto)
    assert r.data_processamento != ""


def test_num_caracteres_consistente_com_texto():
    """num_caracteres deve sempre ser igual a len(texto)."""
    t = _texto_extraido(texto="abc", num_caracteres=3)
    assert t.num_caracteres == len(t.texto)


# ── AC3: exatamente um status por documento ───────────────────────────────────

def test_status_extracao_tem_cinco_valores():
    assert len(STATUS_EXTRACAO) == 5
    assert "extraido_com_sucesso" in STATUS_EXTRACAO
    assert "sem_texto_extraivel" in STATUS_EXTRACAO
    assert "erro_na_leitura" in STATUS_EXTRACAO
    assert "documento_nao_encontrado" in STATUS_EXTRACAO
    assert "nao_elegivel_para_extracao" in STATUS_EXTRACAO


def test_cada_documento_tem_exatamente_um_status():
    """Todos os documentos processados devem ter um status definido e válido."""
    docs = [
        _doc(id="d1", caminho="CCT/SP/Sindpd/a.pdf", nome_arquivo="a.pdf"),
        _doc(id="d2", caminho="CCT/RJ/Sindpd/b.pdf", nome_arquivo="b.pdf", uf=None),
    ]
    registro = {d.caminho: d for d in docs}

    with tempfile.TemporaryDirectory() as tmpdir:
        raiz = Path(tmpdir)
        resultados = processar_extracao(registro, raiz)

    assert len(resultados) == len(docs)
    for r in resultados:
        assert r.status in STATUS_EXTRACAO, f"status inválido: {r.status}"


# ── AC4: PDFs sem texto tratados sem interrupção ──────────────────────────────

def test_pdf_sem_texto_recebe_status_sem_texto_extraivel():
    """PDF que retorna texto vazio deve receber sem_texto_extraivel, não exceção."""
    doc = _doc()
    registro = {doc.caminho: doc}

    with tempfile.TemporaryDirectory() as tmpdir:
        raiz = Path(tmpdir)
        pdf_path = raiz / doc.caminho
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.touch()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("src.services.extractor.pypdf") as mock_pypdf:
            mock_pypdf.PdfReader.return_value = mock_reader
            resultados = processar_extracao(registro, raiz)

    assert resultados[0].status == "sem_texto_extraivel"
    assert resultados[0].texto == ""
    assert resultados[0].num_caracteres == 0


def test_pdf_nao_encontrado_recebe_status_documento_nao_encontrado():
    """Arquivo físico ausente deve receber documento_nao_encontrado."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "inexistente.pdf"
        texto, status = extrair_texto_pdf(pdf_path)
    assert status == "documento_nao_encontrado"
    assert texto == ""


def test_pdf_corrompido_recebe_status_erro_na_leitura():
    """Erro ao abrir PDF deve resultar em erro_na_leitura, sem exceção propagada."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "corrompido.pdf"
        pdf_path.write_bytes(b"not a valid pdf")

        with patch("src.services.extractor.pypdf") as mock_pypdf:
            mock_pypdf.PdfReader.side_effect = Exception("PDF corrompido")
            texto, status = extrair_texto_pdf(pdf_path)

    assert status == "erro_na_leitura"
    assert texto == ""


def test_pdf_com_pagina_falha_coleta_texto_das_demais():
    """Falha em uma página não descarta texto extraído das outras."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "parcial.pdf"
        pdf_path.touch()

        mock_page_ok = MagicMock()
        mock_page_ok.extract_text.return_value = "Texto da página 1."
        mock_page_fail = MagicMock()
        mock_page_fail.extract_text.side_effect = Exception("falha na página")
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page_ok, mock_page_fail]

        with patch("src.services.extractor.pypdf") as mock_pypdf:
            mock_pypdf.PdfReader.return_value = mock_reader
            texto, status = extrair_texto_pdf(pdf_path)

    assert status == "extraido_com_sucesso"
    assert "Texto da página 1." in texto


def test_pdf_com_todas_paginas_falhando_recebe_erro_na_leitura():
    """Quando todas as páginas falham, deve retornar erro_na_leitura."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "falha_total.pdf"
        pdf_path.touch()

        mock_page = MagicMock()
        mock_page.extract_text.side_effect = Exception("falha")
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page, mock_page]

        with patch("src.services.extractor.pypdf") as mock_pypdf:
            mock_pypdf.PdfReader.return_value = mock_reader
            texto, status = extrair_texto_pdf(pdf_path)

    assert status == "erro_na_leitura"
    assert texto == ""


def test_pdf_com_texto_apenas_whitespace_recebe_sem_texto_extraivel():
    """PDF que retorna apenas espaços/newlines deve ser tratado como sem texto."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "whitespace.pdf"
        pdf_path.touch()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "   \n\t  "
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("src.services.extractor.pypdf") as mock_pypdf:
            mock_pypdf.PdfReader.return_value = mock_reader
            texto, status = extrair_texto_pdf(pdf_path)

    assert status == "sem_texto_extraivel"


def test_extracao_continua_apos_documento_nao_encontrado():
    """Arquivo ausente não deve interromper o processamento dos demais."""
    doc_ausente = _doc(id="d1", caminho="CCT/SP/X/ausente.pdf", nome_arquivo="ausente.pdf")
    doc_invalido = _doc(id="d2", caminho="CCT/??/X/inv.pdf", nome_arquivo="inv.pdf", uf=None)
    registro = {
        doc_ausente.caminho: doc_ausente,
        doc_invalido.caminho: doc_invalido,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        resultados = processar_extracao(registro, Path(tmpdir))

    assert len(resultados) == 2
    statuses = {r.caminho: r.status for r in resultados}
    assert statuses[doc_ausente.caminho] == "documento_nao_encontrado"
    assert statuses[doc_invalido.caminho] == "nao_elegivel_para_extracao"


# ── AC5: relatório consolidado ────────────────────────────────────────────────

def test_relatorio_soma_igual_ao_total():
    """A soma dos cinco contadores deve ser igual ao total de documentos."""
    textos = [
        _texto_extraido(caminho="a.pdf", status="extraido_com_sucesso"),
        _texto_extraido(caminho="b.pdf", status="sem_texto_extraivel"),
        _texto_extraido(caminho="c.pdf", status="erro_na_leitura"),
        _texto_extraido(caminho="d.pdf", status="documento_nao_encontrado"),
        _texto_extraido(caminho="e.pdf", status="nao_elegivel_para_extracao"),
    ]

    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_extracao(textos)

    conteudo = "\n".join(capturado)
    assert "5" in conteudo
    assert "✓" in conteudo  # soma consistente


def test_relatorio_com_registro_vazio():
    """Relatório com lista vazia deve exibir zeros e soma consistente."""
    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_extracao([])

    conteudo = "\n".join(capturado)
    assert "✓" in conteudo


# ── Persistência: salvar e carregar ───────────────────────────────────────────

def test_salvar_e_carregar_textos_roundtrip():
    """Deve ser possível salvar e recuperar textos extraídos sem perda de dados."""
    textos = [
        _texto_extraido(caminho="a.pdf", texto="Conteúdo A", num_caracteres=10),
        _texto_extraido(caminho="b.pdf", texto="", num_caracteres=0, status="sem_texto_extraivel"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "textos.json"
        salvar_textos(output_path, textos)
        recuperados = carregar_textos(output_path)

    assert len(recuperados) == 2
    assert recuperados[0].caminho == "a.pdf"
    assert recuperados[0].texto == "Conteúdo A"
    assert recuperados[1].status == "sem_texto_extraivel"


def test_carregar_textos_arquivo_inexistente_retorna_lista_vazia():
    """Carregar de arquivo inexistente deve retornar lista vazia."""
    resultado = carregar_textos(Path("/tmp/nao_existe_jamais.json"))
    assert resultado == []


def test_salvar_textos_escrita_atomica():
    """O arquivo de saída deve existir e ser JSON válido após salvar."""
    textos = [_texto_extraido()]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "sub" / "textos.json"
        salvar_textos(output_path, textos)
        assert output_path.exists()
        with output_path.open(encoding="utf-8") as f:
            dados = json.load(f)
        assert "textos" in dados
        assert len(dados["textos"]) == 1


# ── Ordenação determinística ──────────────────────────────────────────────────

def test_resultados_ordenados_por_caminho():
    """processar_extracao deve retornar documentos ordenados por caminho."""
    docs = [
        _doc(id="d3", caminho="CCT/SP/Z/c.pdf", nome_arquivo="c.pdf"),
        _doc(id="d1", caminho="CCT/AC/A/a.pdf", nome_arquivo="a.pdf"),
        _doc(id="d2", caminho="CCT/MG/B/b.pdf", nome_arquivo="b.pdf"),
    ]
    registro = {d.caminho: d for d in docs}

    with tempfile.TemporaryDirectory() as tmpdir:
        resultados = processar_extracao(registro, Path(tmpdir))

    caminhos = [r.caminho for r in resultados]
    assert caminhos == sorted(caminhos)


# ── runner ────────────────────────────────────────────────────────────────────

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
