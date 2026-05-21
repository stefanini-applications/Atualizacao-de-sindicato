# Guia Operacional do Pipeline de Atualização Sindical

Este documento cobre a jornada completa desde a deposição dos PDFs das CCTs até a geração de `data/base_parametros_sindicais.json`, arquivo consumido pelo Ratecard como fonte canônica de parâmetros sindicais. Siga este guia sem consultar o código-fonte.

---

## Índice

1. [Pré-requisitos de ambiente](#1-pré-requisitos-de-ambiente)
2. [Onde depositar os PDFs das CCTs](#2-onde-depositar-os-pdfs-das-ccts)
3. [Sequência completa dos 15 comandos](#3-sequência-completa-dos-15-comandos)
4. [Pontos de revisão manual](#4-pontos-de-revisão-manual)
5. [Geração da base do Ratecard](#5-geração-da-base-do-ratecard)
6. [Conflitos em `base_parametros_sindicais.json`](#6-conflitos-em-base_parametros_sindicaisjson)
7. [O que o Ratecard deve consumir](#7-o-que-o-ratecard-deve-consumir)

---

## 1. Pré-requisitos de ambiente

### 1.1 Dependências de sistema (Linux/Debian/Ubuntu)

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils
```

| Pacote              | Finalidade                                           |
|---------------------|------------------------------------------------------|
| `tesseract-ocr`     | Motor de OCR para reconhecimento de texto em imagens |
| `tesseract-ocr-por` | Modelo de idioma português para o Tesseract          |
| `poppler-utils`     | Conversão de páginas PDF em imagem (`pdftoppm`)      |

### 1.2 Dependências Python

```bash
pip install -r requirements.txt
```

### 1.3 Validação do ambiente de OCR

Execute este comando **imediatamente antes de iniciar a etapa de OCR** (passo 4), não apenas no momento da instalação. O ambiente pode mudar entre execuções do pipeline:

```bash
python -m src check-ocr-env
```

O comando imprime um relatório em tela indicando se todas as dependências estão disponíveis. **Não prossiga para a etapa de OCR se o relatório indicar dependências ausentes.**

---

## 2. Onde depositar os PDFs das CCTs

Deposite os arquivos PDF na pasta `CCT/`, organizados em subpastas por estado e município:

```
CCT/
├── SP/
│   └── SaoPaulo/
│       ├── sindicato_xyz_2024.pdf
│       └── sindicato_abc_2024.pdf
├── RJ/
│   └── RioDeJaneiro/
│       └── sindicato_def_2024.pdf
└── MG/
    └── BeloHorizonte/
        └── sindicato_ghi_2024.pdf
```

> ⚠️ **Atenção:** Depositar PDFs fora da estrutura `CCT/<ESTADO>/<MUNICIPIO>/` pode produzir registros com campos críticos ausentes, impedindo a extração de texto. Execute `python -m src list --invalid-only` para identificar documentos com problemas de cadastro após o `scan`.

---

## 3. Sequência completa dos 15 comandos

Execute os comandos na ordem abaixo. Cada comando depende da saída do anterior; executar fora de sequência produz arquivos vazios ou erros silenciosos que contaminam a base de pricing.

| #  | Comando | Entrada principal | Saída principal |
|----|---------|-------------------|-----------------|
| 1  | `scan` | `CCT/` (pasta) | `data/registro_documentos.json` |
| 2  | `extract` | `data/registro_documentos.json` | `data/textos_extraidos.json` |
| 3  | `check-ocr-env` | — (verificação de ambiente) | — (relatório em tela) |
| 4  | `ocr` | `data/textos_extraidos.json` | `data/textos_ocr.json` |
| 5  | `consolidate-texts` | `data/textos_extraidos.json` + `data/textos_ocr.json` | `data/textos_consolidados.json` |
| 6  | `identify-clauses` | `data/textos_consolidados.json` | `data/clausulas_candidatas.json` |
| 7  | `extract-adjustments` | `data/clausulas_candidatas.json` | `data/reajustes_extraidos.json` |
| 8  | `validate-adjustments` | `data/reajustes_extraidos.json` | `data/reajustes_para_validacao.json` |
| 9  | `review-adjustments --responsavel "nome.operador"` ⚠️ | `data/reajustes_para_validacao.json` | `data/reajustes_para_validacao.json` |
| 10 | `generate-approved-adjustments` | `data/reajustes_para_validacao.json` | `data/reajustes_aprovados.json` |
| 11 | `preview-pricing-update` | `data/reajustes_aprovados.json` + `data/base_pricing.xlsx` | `data/preview_atualizacao_pricing.xlsx` |
| 12 | `review-pricing-preview` ⚠️ | `data/preview_atualizacao_pricing.xlsx` | — (revisão manual no arquivo) |
| 13 | `generate-pricing-application-base` | `data/preview_atualizacao_pricing.xlsx` | `data/aplicacoes_pricing_aprovadas.xlsx` |
| 14 | `apply-pricing-updates --value-column "coluna"` ⚠️ | `data/aplicacoes_pricing_aprovadas.xlsx` + `data/base_pricing.xlsx` | `data/base_pricing_atualizada.xlsx` |
| 15 | `export-params` | `data/reajustes_aprovados.json` | `data/base_parametros_sindicais.json` |

⚠️ = etapa com argumento obrigatório ou ponto de revisão manual que bloqueia o prosseguimento.

### Comandos prontos para copiar

```bash
# Passo 1 — Varrer pasta de CCTs e registrar documentos
python -m src scan

# Passo 2 — Extrair texto dos PDFs
python -m src extract

# Passo 3 — Validar ambiente de OCR (obrigatório antes do OCR)
python -m src check-ocr-env

# Passo 4 — Executar OCR nos PDFs sem texto extraível
python -m src ocr

# Passo 5 — Consolidar textos extraídos e OCR
python -m src consolidate-texts

# Passo 6 — Identificar cláusulas candidatas a reajuste
python -m src identify-clauses

# Passo 7 — Extrair reajustes das cláusulas identificadas
python -m src extract-adjustments

# Passo 8 — Validar reajustes extraídos
python -m src validate-adjustments

# Passo 9 — REVISÃO MANUAL: revisar reajustes (--responsavel é obrigatório)
python -m src review-adjustments --responsavel "nome.operador"

# Passo 10 — Gerar base de reajustes aprovados
python -m src generate-approved-adjustments

# Passo 11 — Gerar prévia de atualização de pricing
python -m src preview-pricing-update

# Passo 12 — REVISÃO MANUAL: revisar prévia de pricing
python -m src review-pricing-preview

# Passo 13 — Gerar base de aplicações de pricing aprovadas
python -m src generate-pricing-application-base

# Passo 14 — Aplicar reajustes na base de pricing (--value-column é obrigatório)
python -m src apply-pricing-updates --value-column "nome_da_coluna"

# Passo 15 — Exportar parâmetros sindicais para o Ratecard
python -m src export-params
```

---

## 4. Pontos de revisão manual

Existem dois pontos no pipeline onde a execução **deve ser interrompida** para revisão humana antes de prosseguir. Avançar sem a revisão concluída propaga reajustes incorretos ou não rastreados até a base de pricing.

### 4.1 Passo 9 — `review-adjustments` (argumento `--responsavel` obrigatório)

```bash
python -m src review-adjustments --responsavel "nome.operador"
```

**Argumento obrigatório:** `--responsavel "nome.operador"` — identifica o responsável pela revisão. O nome é registrado no campo `responsavel_validacao` de cada registro. A omissão deste argumento causa erro e impede a execução do comando.

**O que verificar:**
- Cada reajuste extraído possui sindicato, período de vigência e percentual de reajuste corretos.
- Os valores percentuais são plausíveis (ex.: não negativos, não superiores a limites históricos razoáveis).
- A fonte (cláusula da CCT) corresponde ao reajuste registrado.

**Como registrar aprovação ou rejeição:**
- O comando exibe cada registro e solicita a decisão do operador (`aprovar` / `rejeitar`).
- A decisão é gravada no campo `status_validacao` do arquivo `data/reajustes_para_validacao.json`.
- Registros rejeitados não avançam para a base de reajustes aprovados.

**Não prossiga para o passo 10 antes de concluir a revisão de todos os registros.**

---

### 4.2 Passo 12 — `review-pricing-preview`

```bash
python -m src review-pricing-preview
```

**O que verificar:**
- Abra `data/preview_atualizacao_pricing.xlsx` e confira a correspondência entre cada reajuste aprovado e a linha da base de pricing afetada.
- Verifique se o sindicato e o período de vigência do reajuste batem com os dados da base de pricing.
- Confirme que o percentual de reajuste que será aplicado está correto.

**Como registrar aprovação ou rejeição:**
- Preencha a coluna `decisao_aplicacao` no arquivo `data/preview_atualizacao_pricing.xlsx` com `aprovado` ou `rejeitado` para cada linha.
- Salve o arquivo antes de executar o próximo comando.
- O comando `review-pricing-preview` verifica se a coluna `decisao_aplicacao` existe e está preenchida; sem isso, o passo 13 não gera saída útil.

**Não prossiga para o passo 13 antes de preencher e salvar as decisões na planilha.**

---

### 4.3 Argumento obrigatório no Passo 14 — `apply-pricing-updates`

```bash
python -m src apply-pricing-updates --value-column "nome_da_coluna"
```

**Argumento obrigatório:** `--value-column "nome_da_coluna"` — especifica o nome exato da coluna da planilha `data/base_pricing.xlsx` sobre a qual o percentual de reajuste será aplicado. A omissão deste argumento causa erro e impede a execução do comando.

> Consulte o responsável pela base de pricing para confirmar o nome correto da coluna antes de executar este passo.

---

## 5. Geração da base do Ratecard

O arquivo final gerado pelo pipeline é `data/base_parametros_sindicais.json`, produzido pelo passo 15:

```bash
python -m src export-params
```

Este comando lê `data/reajustes_aprovados.json` e consolida os parâmetros sindicais no formato canônico esperado pelo Ratecard, resolvendo automaticamente conflitos de múltiplos reajustes para o mesmo sindicato/período (ver seção 6).

Após a execução, verifique que o arquivo `data/base_parametros_sindicais.json` foi gerado e que seu conteúdo é consistente com os reajustes aprovados nas revisões manuais anteriores.

---

## 6. Conflitos em `base_parametros_sindicais.json`

### O que é um conflito

Um conflito ocorre quando o mesmo sindicato possui **mais de um reajuste aprovado para o mesmo período** (ex.: negociações parciais, aditivos ou reprocessamentos de CCTs com vigências sobrepostas).

### Consolidação automática

O comando `export-params` (passo 15) consolida automaticamente os registros conflitantes ao gerar `data/base_parametros_sindicais.json`. A regra padrão de priorização é a seguinte: **o registro mais recente** (maior data de processamento) prevalece sobre registros anteriores para o mesmo sindicato/período.

### Quando intervir manualmente

Se a consolidação automática não for suficiente — por exemplo, quando dois reajustes para o mesmo sindicato/período têm datas de processamento idênticas ou quando a regra de prioridade automática não reflete o acordo correto —, o operador deve:

1. Abrir `data/base_parametros_sindicais.json` em um editor de texto ou JSON.
2. Identificar os registros duplicados (mesmo `sindicato` e mesmo `periodo_vigencia`).
3. Remover ou corrigir manualmente o registro incorreto, mantendo apenas o registro que reflete o acordo sindical vigente.
4. Salvar o arquivo antes de disponibilizá-lo ao Ratecard.

> ⚠️ **Atenção:** Edite **apenas** `data/base_parametros_sindicais.json`. Nunca edite arquivos intermediários como `data/reajustes_aprovados.json` para resolver conflitos na saída final, pois isso pode reintroduzir os conflitos em execuções futuras do pipeline.

### Como identificar conflitos

Para verificar se existem conflitos antes de disponibilizar o arquivo ao Ratecard, execute:

```bash
python -c "
import json, collections
with open('data/base_parametros_sindicais.json') as f:
    registros = json.load(f)
chaves = [(r['sindicato'], r['periodo_vigencia']) for r in registros]
duplicados = [c for c, n in collections.Counter(chaves).items() if n > 1]
if duplicados:
    print(f'{len(duplicados)} conflito(s) encontrado(s):')
    for s, p in duplicados:
        print(f'  Sindicato: {s} | Período: {p}')
else:
    print('Nenhum conflito encontrado.')
"
```

---

## 7. O que o Ratecard deve consumir

O Ratecard deve consumir **exclusivamente**:

```
data/base_parametros_sindicais.json
```

Este é o único arquivo final do pipeline, consolidado e validado, gerado pelo comando `export-params`.

> ⛔ **Nunca forneça ao Ratecard arquivos intermediários**, como:
> - `data/reajustes_aprovados.json` — pode conter registros não consolidados ou com conflitos não resolvidos.
> - `data/reajustes_para_validacao.json` — contém registros ainda pendentes de revisão humana.
> - `data/preview_atualizacao_pricing.xlsx` — é uma prévia de correspondência, não a base final.
> - Qualquer outro arquivo em `data/` que não seja `base_parametros_sindicais.json`.

O uso de arquivos intermediários pelo Ratecard pode resultar em aplicação de parâmetros desatualizados, duplicados ou com conflitos não resolvidos, gerando erro de precificação.
