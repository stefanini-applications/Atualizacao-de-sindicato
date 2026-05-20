# Atualizacao-de-sindicato

Ferramentas para estruturação da base de Convenções Coletivas de Trabalho (CCTs).

## Dependências de sistema

Antes de executar os comandos de OCR, instale as seguintes dependências no sistema operacional:

### Linux/Debian (Ubuntu)

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils
```

| Pacote              | Finalidade                                          |
|---------------------|-----------------------------------------------------|
| `tesseract-ocr`     | Motor de OCR para reconhecimento de texto em imagens |
| `tesseract-ocr-por` | Modelo de idioma português para o Tesseract          |
| `poppler-utils`     | Conversão de páginas de PDF em imagem (`pdftoppm`)  |

### Verificação

```bash
tesseract --version       # deve exibir a versão instalada
tesseract --list-langs    # deve listar "por" entre os idiomas
pdftoppm -v               # deve exibir a versão do Poppler
```

## Dependências Python

```bash
pip install -r requirements.txt
```

## Uso

```bash
python -m src scan                # varre a pasta CCT/ e atualiza o registro
python -m src extract             # extrai texto dos PDFs
python -m src ocr                 # executa OCR nos PDFs sem texto extraível
python -m src check-ocr-env       # verifica dependências de OCR no ambiente
python -m src list                # lista documentos do registro
python -m src summary             # exibe resumo estatístico
```
