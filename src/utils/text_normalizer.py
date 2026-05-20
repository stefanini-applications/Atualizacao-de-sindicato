"""Utilitário de normalização de texto para correspondência de palavras-chave.

Aplica transformações de forma sequencial:
  (a) conversão para minúsculas;
  (b) remoção de acentos e diacríticos via NFD + filtragem de categoria Mn;
  (c) substituição de hífen e variantes por espaço;
  (d) colapso de espaços em branco múltiplos.

O texto original nunca é modificado em outros contextos; esta função é usada
exclusivamente durante a fase de correspondência (AC6).
"""

import re
import unicodedata


_RE_HIFENS = re.compile(r"[\u002D\u2010\u2011\u2012\u2013\u2014\u2015]")
_RE_ESPACOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Retorna versão normalizada de *texto* para comparação com termos-chave.

    Passos:
      1. Minúsculas.
      2. NFD → remove categorias Unicode Mn (marcas de acento).
      3. Hifens e travessões → espaço simples.
      4. Colapso de espaços e tabulações em espaço único; strip lateral.
    """
    texto = texto.lower()
    nfd = unicodedata.normalize("NFD", texto)
    sem_acentos = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    sem_hifens = _RE_HIFENS.sub(" ", sem_acentos)
    return _RE_ESPACOS.sub(" ", sem_hifens).strip()
