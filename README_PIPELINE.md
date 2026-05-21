# Guia Operacional do Pipeline de Atualização Sindical

Este documento cobre a execução completa do pipeline de atualização sindical: desde a deposição dos PDFs das CCTs até a geração de `data/base_parametros_sindicais.json`, o arquivo canônico consumido pelo Ratecard como fonte de parâmetros sindicais.

---

## Sumário

1. [Pré-requisitos de ambiente](#1-pré-requisitos-de-ambiente)
2. [Onde depositar os PDFs das CCTs](#2-onde-depositar-os-pdfs-das-ccts)
3. [Sequência completa de comandos](#3-sequência-completa-de-comandos)
4. [Arquivos gerados por cada comando](#4-arquivos-gerados-por-cada-comando)
5. [Pontos de revisão manual](#5-pontos-de-revisão-manual)
6. [Como gerar a base do Ratecard](#6-como-gerar-a-base-do-ratecard)
7. [Conflitos em `base_parametros_sindicais.json`](#7-conflitos-em-base_parametros_sindicaisjson)

---

## 1. Pré-requisitos de ambiente

Antes de iniciar o pipeline, verifique se todas as dependências estão instaladas.

### Dependências de sistema (Linux/Debian/Ubuntu)

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils
```

| Pacote              | Finalidade                                           |
|---------------------|------------------------------------------------------|
| `tesseract-ocr`     | Motor de OCR para reconhecimento de texto em imagens |
| `tesseract-ocr-por` | Modelo de idioma português para o Tesseract          |
| `poppler-utils`     | Conversão de páginas de PDF em imagem (`pdftoppm`)   |

### Dependências Python

```bash
pip install -r requirements.txt
```

### Validação do ambiente de OCR

Execute este comando **antes de iniciar a etapa de OCR** (não apenas na instalação, pois o ambiente pode mudar entre execuções):

```bash
python -m src check-ocr-env
```

A ausência das dependências de OCR é a causa mais comum de falha silenciosa no reconhecimento de texto, resultando em documentos processados com texto vazio.

---

## 2. Onde depositar os PDFs das CCTs

Os PDFs das Convenções Coletivas de Trabalho devem ser depositados na pasta `CCT/`, organizada em subpastas por **estado** e **município**:

```
CCT/
└── <UF>/
    └── <Município>/
        └── <arquivo>.pdf
```

**Exemplos de caminhos válidos:**

```
CCT/SP/SaoPaulo/sindicato_xyz_2024.pdf
CCT/RJ/RioDeJaneiro/cct_comerciarios_2024.pdf
CCT/MG/BeloHorizonte/acordo_metalurgicos_2025.pdf
```

> ⚠️ O comando `scan` localiza os documentos percorrendo recursivamente a estrutura `CCT/`. Se os PDFs não estiverem nessa pasta, o pipeline não os encontrará.

---

## 3. Sequência completa de comandos

Execute os comandos **nesta ordem exata**. Executar fora de ordem produz arquivos vazios ou erros silenciosos que contaminam a base de pricing.

```bash
# 1. Varre a pasta CCT/ e registra os documentos encontrados
python -m src scan

# 2. Extrai texto bruto dos PDFs cadastrados no registro
python -m src extract

# 3. Verifica se o ambiente possui as dependências necessárias para OCR
#    ⚠️  Execute SEMPRE antes do passo 4
python -m src check-ocr-env

# 4. Executa OCR nos PDFs sem texto extraível (digitalizados/imagem)
python -m src ocr

# 5. Consolida as bases de extração nativa e OCR em uma fonte única
python -m src consolidate-texts

# 6. Identifica cláusulas salariais e de benefícios na base consolidada
python -m src identify-clauses

# 7. Extrai dados estruturados de reajuste salarial e vigência das cláusulas
python -m src extract-adjustments

# 8. Classifica cada reajuste extraído com um status de validação inicial
python -m src validate-adjustments

# ════════════════════════════════════════════════════════
# PONTO DE REVISÃO MANUAL 1 — veja seção 5.1
# ════════════════════════════════════════════════════════
# 9. Aplica a revisão manual sobre os registros editados pelo operador
#    ⚠️  --responsavel é OBRIGATÓRIO
python -m src review-adjustments --responsavel "nome.operador"

# 10. Gera a base final de reajustes aprovados para uso no pricing
python -m src generate-approved-adjustments

# 11. Gera prévia de correspondência entre reajustes aprovados e base de pricing
python -m src preview-pricing-update

# ════════════════════════════════════════════════════════
# PONTO DE REVISÃO MANUAL 2 — veja seção 5.2
# ════════════════════════════════════════════════════════
# 12. Exibe estado da prévia e garante coluna decisao_aplicacao
python -m src review-pricing-preview

# 13. Gera base de aplicações aprovadas a partir da prévia revisada
python -m src generate-pricing-application-base

# 14. Aplica reajustes aprovados sobre a base de pricing e gera base atualizada
#    ⚠️  --value-column é OBRIGATÓRIO
python -m src apply-pricing-updates --value-column "valor_pricing"

# 15. Gera base consultável de parâmetros sindicais para o Ratecard
python -m src export-params
```

---

## 4. Arquivos gerados por cada comando

| # | Comando                         | Arquivo de entrada principal              | Arquivo de saída principal                       |
|---|---------------------------------|-------------------------------------------|--------------------------------------------------|
| 1 | `scan`                          | `CCT/` (pasta)                            | `data/registro_documentos.json`                  |
| 2 | `extract`                       | `data/registro_documentos.json`           | `data/textos_extraidos.json`                     |
| 3 | `check-ocr-env`                 | — (verificação de ambiente)               | — (saída no terminal)                            |
| 4 | `ocr`                           | `data/textos_extraidos.json`              | `data/textos_ocr.json`                           |
| 5 | `consolidate-texts`             | `data/textos_extraidos.json` + `data/textos_ocr.json` | `data/textos_consolidados.json`    |
| 6 | `identify-clauses`              | `data/textos_consolidados.json`           | `data/clausulas_candidatas.json`                 |
| 7 | `extract-adjustments`           | `data/clausulas_candidatas.json`          | `data/reajustes_extraidos.json`                  |
| 8 | `validate-adjustments`          | `data/reajustes_extraidos.json`           | `data/reajustes_para_validacao.json`             |
| 9 | `review-adjustments`            | `data/reajustes_para_validacao.json`      | `data/reajustes_para_validacao.json` (atualizado)|
|10 | `generate-approved-adjustments` | `data/reajustes_para_validacao.json`      | `data/reajustes_aprovados.json`                  |
|11 | `preview-pricing-update`        | `data/reajustes_aprovados.json` + `data/base_pricing.xlsx` | `data/preview_atualizacao_pricing.xlsx` |
|12 | `review-pricing-preview`        | `data/preview_atualizacao_pricing.xlsx`   | `data/preview_atualizacao_pricing.xlsx` (atualizado) |
|13 | `generate-pricing-application-base` | `data/preview_atualizacao_pricing.xlsx` | `data/aplicacoes_pricing_aprovadas.xlsx`      |
|14 | `apply-pricing-updates`         | `data/base_pricing.xlsx` + `data/aplicacoes_pricing_aprovadas.xlsx` | `data/base_pricing_atualizada.xlsx` |
|15 | `export-params`                 | `data/reajustes_aprovados.json`           | `data/base_parametros_sindicais.json`            |

---

## 5. Pontos de revisão manual

O pipeline possui **dois pontos de revisão manual obrigatórios**. A execução **não deve prosseguir** enquanto a revisão não estiver concluída.

### 5.1 Revisão de reajustes — entre os passos 8 e 9

**Quando:** Após `validate-adjustments` (passo 8), antes de `review-adjustments` (passo 9).

**O que revisar:** Abra o arquivo `data/reajustes_para_validacao.json` e verifique cada registro:

- **Percentual de reajuste** — confirme se o valor extraído bate com o texto da cláusula.
- **Sindicato e UF** — verifique se estão corretos.
- **Período de vigência** — confirme as datas de início e fim.
- **Status de validação** — marque cada registro como `aprovado` ou `rejeitado` no campo correspondente; corrija os campos com erros antes de aprovar.

**Como registrar a decisão:** Edite o arquivo JSON diretamente, ajustando o campo de status de cada registro. Em seguida, execute o comando de revisão com seu nome de operador:

```bash
python -m src review-adjustments --responsavel "nome.operador"
```

> ⚠️ **`--responsavel` é obrigatório.** O argumento é declarado como `required=True` e o pipeline rejeita a execução sem ele. Use o seu nome de login ou identificador oficial do time (ex.: `"joao.silva"`). Esse valor é gravado no campo `responsavel_validacao` de cada registro revisado para rastreabilidade.

**Rejeição:** Registros marcados como `rejeitado` não avançarão para a base de reajustes aprovados. Se todos os registros forem rejeitados, o passo 10 (`generate-approved-adjustments`) emitirá aviso e retornará erro.

---

### 5.2 Revisão da prévia de pricing — entre os passos 11 e 13

**Quando:** Após `preview-pricing-update` (passo 11), antes de `generate-pricing-application-base` (passo 13).

**O que revisar:** Abra o arquivo `data/preview_atualizacao_pricing.xlsx` e, para cada linha, verifique:

- **`status_aplicacao`** — identifica o resultado do cruzamento (ex.: `reajuste_encontrado`, sem correspondência). Revise as linhas com `reajuste_encontrado` para confirmar que a correspondência está correta.
- **Sindicato, UF e ano** — confirme que o reajuste foi associado à linha correta da base de pricing.
- **Percentual** — valide o valor a ser aplicado.

**Como registrar a decisão:** Execute primeiro o comando de revisão para garantir a coluna `decisao_aplicacao`:

```bash
python -m src review-pricing-preview
```

Em seguida, abra o arquivo `.xlsx` e preencha a coluna `decisao_aplicacao` com `aprovado` ou `rejeitado` para cada linha. Salve o arquivo antes de prosseguir.

**Rejeição:** Somente as linhas com `decisao_aplicacao = aprovado` **e** `status_aplicacao = reajuste_encontrado` avançam para o passo 13. Linhas rejeitadas ou sem decisão são ignoradas.

---

## 6. Como gerar a base do Ratecard

O arquivo final consumido pelo Ratecard é **`data/base_parametros_sindicais.json`**, gerado pelo passo 15:

```bash
python -m src export-params
```

Este comando lê `data/reajustes_aprovados.json` (produzido no passo 10) e exporta os parâmetros sindicais consolidados em formato consultável.

> ⚠️ **O Ratecard deve consumir exclusivamente `data/base_parametros_sindicais.json`.**
> Nunca utilize arquivos intermediários como `data/reajustes_aprovados.json` como fonte para o Ratecard — esses arquivos podem conter registros ainda não consolidados ou com conflitos não resolvidos, gerando erro de precificação.

---

## 7. Conflitos em `base_parametros_sindicais.json`

### O que é um conflito

Um conflito ocorre quando o mesmo sindicato possui **mais de um reajuste aprovado para o mesmo período** — situação comum em negociações parciais, aditivos ou retificações de CCT.

### Consolidação automática

O pipeline (passo 15, `export-params`) detecta e consolida esses registros automaticamente ao gerar `data/base_parametros_sindicais.json`. O relatório exibido ao final do comando informa quantos conflitos foram encontrados e como foram tratados.

### Intervenção manual

Quando a consolidação automática **não for suficiente** (ex.: dois reajustes com percentuais distintos para o mesmo sindicato/período onde ambos são tecnicamente válidos), siga este procedimento:

1. Identifique os registros em conflito em `data/reajustes_aprovados.json` — procure por entradas com mesmo sindicato, UF e período de vigência.
2. Retorne ao passo 9 (`review-adjustments`) e **rejeite** os registros duplicados ou incorretos, mantendo apenas o reajuste definitivo como `aprovado`.
3. Execute novamente os passos 10 a 15 para regenerar a base sem o conflito.
4. Se a intervenção for urgente e o pipeline completo não puder ser re-executado, edite `data/base_parametros_sindicais.json` diretamente, removendo ou corrigindo a entrada em conflito, **antes** de disponibilizar o arquivo ao Ratecard.

> ⚠️ Após qualquer edição manual em `data/base_parametros_sindicais.json`, documente a alteração (data, operador, motivo) em comentário no próprio JSON ou em registro separado, para manter a rastreabilidade.
