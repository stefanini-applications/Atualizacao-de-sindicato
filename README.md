# Atualizacao-de-sindicato

## Dependências de sistema para OCR

O comando `ocr` requer as seguintes dependências externas além dos pacotes Python:

```bash
# Tesseract OCR e dados de língua portuguesa
apt install tesseract-ocr tesseract-ocr-por

# Poppler utilities (necessário para pdf2image)
apt install poppler-utils
```

## Instalação dos pacotes Python

```bash
pip install -r requirements.txt
```

## Comandos CLI

```bash
# Varre a pasta CCT/ e atualiza o registro
python -m src scan

# Extrai texto nativo dos PDFs
python -m src extract

# Aplica OCR nos PDFs sem texto extraível (requer Tesseract e Poppler)
python -m src ocr
```
