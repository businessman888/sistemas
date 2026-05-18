"""Converte títulos em nomes de arquivo seguros para o filesystem."""

import re
import unicodedata


def slugify(text: str, max_length: int = 100) -> str:
    """Transforma texto em slug seguro para nomes de arquivo.

    Preserva acentos e caracteres UTF-8 legíveis, mas remove
    caracteres proibidos em filesystems (Windows/macOS/Linux).
    """
    # Normaliza unicode para forma composta (NFC)
    text = unicodedata.normalize("NFC", text)

    # Remove caracteres proibidos em nomes de arquivo
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text)

    # Colapsa espaços múltiplos e underscores
    text = re.sub(r"\s+", " ", text).strip()

    # Trunca preservando palavras inteiras
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0]

    return text


def slugify_tag(text: str) -> str:
    """Gera slug para uso em tags do Obsidian (lowercase, sem acentos, hifenizado)."""
    # Decompõe acentos e remove marcas diacríticas
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Lowercase e substitui espaços/underscores por hífen
    ascii_text = ascii_text.lower().strip()
    ascii_text = re.sub(r"[^a-z0-9\s-]", "", ascii_text)
    ascii_text = re.sub(r"[\s_]+", "-", ascii_text)
    ascii_text = re.sub(r"-+", "-", ascii_text).strip("-")

    return ascii_text
