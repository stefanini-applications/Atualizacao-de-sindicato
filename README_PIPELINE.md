# Guia Operacional — Pipeline de Atualização Sindical

Este guia descreve a execução completa do pipeline de atualização sindical: da deposição dos PDFs das CCTs na pasta `CCT/` até a geração de `data/base_parametros_sindicais.json`, arquivo canônico consumido pelo Ratecard.

---

## 1. Onde depositar os PDFs

Deposite os PDFs das Convenções Coletivas de Trabalho na pasta `CCT/`, organizados em subpastas por estado e município:

```
CCT/
└── SP/
    └── SaoPaulo/
        └── sindicato_xyz_2024.pdf
```

Outros exemplos de caminhos válidos:

```
CCT/MG/BeloHorizonte/sindicato_abc_2025.pdf
CCT/RJ/RioDeJaneiro/sindicato_def_2024.pdf
CCT/RS/PortoAlegre/sindicato_ghi_2025.pdf
```

> **Atenção:** A deposição dos PDFs em caminhos incorretos (fora da estrutura `CCT/<ESTADO>/<MUNICIPIO>/`) impede o reconhecimento automático dos documentos pelo comando `scan` e pode resultar em arquivos de saída vazios.

---

## 2. Pré-requisitos de ambiente

Antes de executar o pipeline, instale as dependências do sistema operacional:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils
```

| Pacote              | Finalidade                                           |
|---------------------|------------------------------------------------------|
| `tesseract-ocr`     | Motor de OCR para reconhecimento de texto em imagens |
| `tesseract-ocr-por` | Modelo de idioma português para o Tesseract          |
| `poppler-utils`     | Conversão de páginas de PDF em imagem (`pdftoppm`)   |

Instale também as dependências Python:

```bash
pip install -r requirements.txt
```

> **Importante:** Execute `python -m src check-ocr-env` imediatamente antes da etapa de OCR (passo 3 da sequência), não apenas no momento de instalação. O ambiente pode mudar entre execuções do pipeline, e a ausência das dependências de OCR é a causa mais comum de falha silenciosa no reconhecimento de texto.

---

## 3. Sequência completa dos 15 comandos

Execute os comandos na ordem abaixo. **Não pule etapas nem altere a sequência** — cada comando depende da saída do anterior.

| # | Comando | Entrada principal | Saída principal |
|---|---------|-------------------|-----------------|
| 1 | `scan` | `CCT/` | `data/registro_documentos.json` |
| 2 | `extract` | `data/registro_documentos.json` | `data/textos_extraidos.json` |
| 3 | `check-ocr-env` | — | — (validação de ambiente) |
| 4 | `ocr` | `data/textos_extraidos.json` | `data/textos_ocr.json` |
| 5 | `consolidate-texts` | `data/textos_extraidos.json` + `data/textos_ocr.json` | `data/textos_consolidados.json` |
| 6 | `identify-clauses` | `data/textos_consolidados.json` | `data/clausulas_candidatas.json` |
| 7 | `extract-adjustments` | `data/clausulas_candidatas.json` | `data/reajustes_extraidos.json` |
| 8 | `validate-adjustments` | `data/reajustes_extraidos.json` | `data/reajustes_para_validacao.json` |
| 9 | `review-adjustments` ⚠️ **REVISÃO MANUAL** | `data/reajustes_para_validacao.json` | `data/reajustes_para_validacao.json` |
| 10 | `generate-approved-adjustments` | `data/reajustes_para_validacao.json` | `data/reajustes_aprovados.json` |
| 11 | `preview-pricing-update` | `data/base_pricing.xlsx` + `data/reajustes_aprovados.json` | `data/preview_atualizacao_pricing.xlsx` |
| 12 | `review-pricing-preview` ⚠️ **REVISÃO MANUAL** | `data/preview_atualizacao_pricing.xlsx` | `data/preview_atualizacao_pricing.xlsx` |
| 13 | `generate-pricing-application-base` | `data/preview_atualizacao_pricing.xlsx` | `data/aplicacoes_pricing_aprovadas.xlsx` |
| 14 | `apply-pricing-updates` | `data/base_pricing.xlsx` + `data/aplicacoes_pricing_aprovadas.xlsx` | `data/base_pricing_atualizada.xlsx` |
| 15 | `export-params` | `data/reajustes_aprovados.json` | `data/base_parametros_sindicais.json` |

### Comandos completos com argumentos padrão

```bash
# 1. Registrar os PDFs depositados em CCT/
python -m src scan

# 2. Extrair texto nativo dos PDFs
python -m src extract

# 3. Verificar dependências de OCR ANTES de executar o OCR
python -m src check-ocr-env

# 4. Executar OCR nos PDFs sem texto extraível
python -m src ocr

# 5. Consolidar extração nativa e OCR em fonte única
python -m src consolidate-texts

# 6. Identificar cláusulas salariais e de benefícios
python -m src identify-clauses

# 7. Extrair dados estruturados de reajuste das cláusulas
python -m src extract-adjustments

# 8. Classificar reajustes com status de validação inicial
python -m src validate-adjustments

# 9. ⚠️  REVISÃO MANUAL — ver seção 4
python -m src review-adjustments --responsavel "nome.operador"

# 10. Gerar base final de reajustes aprovados
python -m src generate-approved-adjustments

# 11. Gerar prévia de aplicação dos reajustes sobre a base de pricing
python -m src preview-pricing-update

# 12. ⚠️  REVISÃO MANUAL — ver seção 4
python -m src review-pricing-preview

# 13. Gerar base de aplicações aprovadas a partir da prévia revisada
python -m src generate-pricing-application-base

# 14. Aplicar reajustes aprovados sobre a base de pricing
python -m src apply-pricing-updates --value-column "valor_pricing"

# 15. Exportar parâmetros sindicais para o Ratecard
python -m src export-params
```

---

## 4. Pontos de revisão manual

O pipeline possui **dois pontos de revisão manual obrigatórios**. A execução **não deve prosseguir** antes de cada revisão estar concluída.

### 4.1 Revisão de reajustes — passo 9

**Comando:**
```bash
python -m src review-adjustments --responsavel "nome.operador"
```

> ⚠️ **`--responsavel` é obrigatório.** A omissão deste argumento causa erro de execução. Use o nome de login ou identificador do operador responsável pela revisão (ex.: `"joao.silva"`). O valor é registrado no campo `responsavel_validacao` de cada registro, garantindo rastreabilidade.

**O que verificar:**
- Abra `data/reajustes_para_validacao.json` em um editor de texto ou planilha.
- Para cada reajuste, analise: sindicato, período de vigência, percentual de reajuste e fonte (trecho do PDF).
- Registre sua decisão no campo `decisao` de cada registro: `"aprovado"` ou `"rejeitado"`.
- Adicione observações no campo `observacao` quando necessário.

**Aprovação / rejeição:**
- Aprovado: `"decisao": "aprovado"` — o reajuste será incluído na base final.
- Rejeitado: `"decisao": "rejeitado"` — o reajuste será descartado e não afetará o pricing.

Após editar o arquivo, execute o comando `review-adjustments` para registrar formalmente a revisão. Somente então execute o passo 10.

---

### 4.2 Revisão da prévia de pricing — passo 12

**Comando:**
```bash
python -m src review-pricing-preview
```

**O que verificar:**
- Abra `data/preview_atualizacao_pricing.xlsx` em uma planilha.
- Verifique a correspondência entre os reajustes aprovados e as linhas da base de pricing: sindicato, período, percentual e coluna de valor a ser aplicada.
- Para cada linha, registre a decisão na coluna `decisao_aplicacao`: `"aprovado"` ou `"rejeitado"`.

**Aprovação / rejeição:**
- Aprovado: a linha será incluída na base de aplicações e o reajuste será efetivado.
- Rejeitado: a linha será descartada e não alterará a base de pricing.

Após preencher a coluna `decisao_aplicacao` em todo o arquivo, salve e execute o passo 13.

---

## 5. Como gerar a base do Ratecard

Após a conclusão dos passos 1–14, execute o passo 15:

```bash
python -m src export-params
```

Este comando lê `data/reajustes_aprovados.json` e gera `data/base_parametros_sindicais.json` — a base canônica de parâmetros sindicais para o Ratecard.

> **O Ratecard deve consumir exclusivamente `data/base_parametros_sindicais.json`.**  
> Nunca utilize arquivos intermediários como `data/reajustes_aprovados.json` como fonte de dados para o Ratecard. Esses arquivos podem conter registros ainda não consolidados ou com conflitos não resolvidos, gerando erro de precificação.

---

## 6. Como interpretar e resolver conflitos em `base_parametros_sindicais.json`

**O que é um conflito:** Ocorre quando o mesmo sindicato possui mais de um reajuste aprovado para o mesmo período (ex.: negociações parciais, aditivos ou retificações de CCT).

**Consolidação automática:** O pipeline consolida automaticamente registros duplicados ao gerar `data/base_parametros_sindicais.json` no passo 15. Em geral, o registro mais recente ou com maior percentual é priorizado conforme as regras internas do comando `export-params`.

**Quando intervir manualmente:** Se a consolidação automática não for suficiente (ex.: dois reajustes aprovados para o mesmo sindicato/período com percentuais conflitantes e fontes distintas), siga este procedimento:

1. Execute `python -m src export-params` para gerar a versão automática.
2. Abra `data/base_parametros_sindicais.json` em um editor de texto.
3. Localize os registros duplicados pelo campo `sindicato` e `periodo_vigencia`.
4. Mantenha apenas o registro correto (ou atualize o campo `percentual_reajuste` com o valor consolidado), removendo os duplicados.
5. Salve o arquivo. **Não execute novamente `export-params`** após a edição manual, pois o comando sobrescreve o arquivo.
6. Comunique a equipe de Ratecard que a edição manual foi realizada e documente a justificativa.

> **Atenção:** Edições manuais em `data/base_parametros_sindicais.json` não são rastreadas pelo pipeline. Registre a intervenção em um canal de controle (ex.: comentário no PR, ticket ou log de operação).

---

## 7. O que o Ratecard deve consumir

| Arquivo | Descrição | Usar no Ratecard? |
|---------|-----------|:-----------------:|
| `data/base_parametros_sindicais.json` | Base canônica de parâmetros sindicais — saída final do pipeline | ✅ **Sim** |
| `data/reajustes_aprovados.json` | Reajustes aprovados na revisão manual — arquivo intermediário | ❌ Não |
| `data/reajustes_para_validacao.json` | Reajustes aguardando ou em revisão — arquivo intermediário | ❌ Não |
| `data/preview_atualizacao_pricing.xlsx` | Prévia de aplicação — arquivo intermediário | ❌ Não |
| `data/aplicacoes_pricing_aprovadas.xlsx` | Base de aplicações aprovadas — arquivo intermediário | ❌ Não |
| `data/base_pricing_atualizada.xlsx` | Base de pricing com reajustes aplicados — uso interno do pipeline | ❌ Não |

**`data/base_parametros_sindicais.json` é o único arquivo gerado pelo pipeline que o Ratecard deve consumir.**

---

## Referência rápida de arquivos gerados

```
data/
├── registro_documentos.json        ← passo  1 (scan)
├── textos_extraidos.json           ← passo  2 (extract)
├── textos_ocr.json                 ← passo  4 (ocr)
├── textos_consolidados.json        ← passo  5 (consolidate-texts)
├── clausulas_candidatas.json       ← passo  6 (identify-clauses)
├── reajustes_extraidos.json        ← passo  7 (extract-adjustments)
├── reajustes_para_validacao.json   ← passo  8 (validate-adjustments)
│                                      passo  9 (review-adjustments) ⚠️
├── reajustes_aprovados.json        ← passo 10 (generate-approved-adjustments)
├── preview_atualizacao_pricing.xlsx← passo 11 (preview-pricing-update)
│                                      passo 12 (review-pricing-preview) ⚠️
├── aplicacoes_pricing_aprovadas.xlsx←passo 13 (generate-pricing-application-base)
├── base_pricing_atualizada.xlsx    ← passo 14 (apply-pricing-updates)
└── base_parametros_sindicais.json  ← passo 15 (export-params) ✅ RATECARD
```
