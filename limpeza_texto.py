# -*- coding: utf-8 -*-
import re, unicodedata
from pathlib import Path

def normalize_unicode(s: str) -> str:
    return unicodedata.normalize("NFC", s)

def remove_page_headers_and_borders(s: str) -> str:
    s = re.sub(r"^=+\s*$", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*PÁGINA\s+\d+\s*$", "", s, flags=re.MULTILINE | re.IGNORECASE)
    return s

def drop_ocr_noise_lines(s: str) -> str:
    cleaned_lines = []
    for line in s.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if re.fullmatch(r"[\|\.\-_,:;`'\"~^°ºª\[\]\(\)\\\/\s]{3,}", stripped):
            continue
        non_alnum_ratio = sum(ch for ch in map(lambda c: 0 if c.isalnum() or c.isspace() else 1, stripped))
        if len(stripped) > 6 and non_alnum_ratio / len(stripped) > 0.6:
            continue
        if re.match(r"^[A-Za-z]{1,2}\s{0,2}[\W_]{2,}$", stripped):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)

def fix_common_ocr_tokens(s: str) -> str:
    replacements = {
        "Código": "Código", "Polícia": "Polícia", "Goiás": "Goiás",
        "82o": "§2º", "8 2o": "§2º", "as": "às",
        "ESTADO DE GOIÁS": "ESTADO DE GOIÁS", "SEGURANÇA PÚBLICA": "SEGURANÇA PÚBLICA",
        "DELEGACIA DE POLÍCIA": "DELEGACIA DE POLÍCIA", "OCORRÊNCIA": "OCORRÊNCIA",
        "COMUNICAÇÃO": "COMUNICAÇÃO", "EXTORSÃO": "EXTORSÃO", "PATRIMÔNIO": "PATRIMÔNIO",
        "TíTULO": "TÍTULO", "RELATO": "RELATO", "VÍTIMAS": "VÍTIMAS", "RESIDÊNCIA": "RESIDÊNCIA",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s

def collapse_dots_and_spaces(s: str) -> str:
    s = re.sub(r"([A-Za-zÀ-ÿ])\.+\s*:", r"\1: ", s)
    s = re.sub(r"\.{3,}", " ", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s

def tidy_bullets_and_headers(s: str) -> str:
    s = re.sub(r"^#+\s*\*?_?\*?\s*(.+?)\s*\*?_?\*?\s*$", r"# \1", s, flags=re.MULTILINE)
    s = s.replace("## 1. Dados Processo", "## 1. Dados do Processo")
    s = s.replace("## 2. Partes Processos:", "## 2. Partes do Processo")
    return s

def extract_structured_markdown(s: str) -> str:
    s = normalize_unicode(s)
    s = remove_page_headers_and_borders(s)
    s = drop_ocr_noise_lines(s)
    s = fix_common_ocr_tokens(s)
    s = collapse_dots_and_spaces(s)
    s = tidy_bullets_and_headers(s)

    s = re.sub(r"#\s*\*?_?Processo Nº:\s*([^\n_]+)_?\*?", r"# Processo nº \1", s)
    s = re.sub(r"(?i)valor da causa:\s*R\$\s*$", "Valor da Causa: Não informado", s)
    s = re.sub(r"(?im)^\s*PORTARIA\s*$", "\n## Portaria Policial\n", s)

    s = re.sub(r"(?im)^\s*Rocio de atendimento.*$", "Registro de Atendimento Integrado (RAI)", s)
    s = re.sub(r"(?im)^.*EMITIDO EM\s*([0-9/]{10})\s*às\s*([0-9:]{4,5}).*$",
               r"- Emitido em: \1 às \2", s)
    s = re.sub(r"(?im)SOLICITANTE:\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ ]+)\s+TELEFONE:\s*([\(\)\d\-\s]+)",
               r"- Solicitante: \1 – Tel: \2", s)
    s = re.sub(r"(?i)DATA DA COMUNICAÇÃO:\s*([0-9/]{10})\s*às\s*([0-9:]{4,5})",
               r"- Data da Comunicação: \1 às \2", s)
    s = re.sub(r"(?i)DATA DO FATO:\s*([0-9/]{10})\s*às\s*([0-9:]{4,5})",
               r"- Data do Fato: \1 às \2", s)
    s = s.replace("Art. 157, §2º", "**Art. 157, §2º**")
    s = re.sub(r"\+\s*ENDEREÇO:\s*(.+?)(?:\n|$)",
               lambda m: "- Endereço: " + re.sub(r"\s*\|\s*", " ", m.group(1)), s)
    s = re.sub(r"(?im)^\s*Página\s+\d+\s+de\s+\d+\.\s*$", "", s)
    return s.strip() + "\n"

def limpar_para_markdown(texto_bruto: str) -> str:
    return extract_structured_markdown(texto_bruto)

if __name__ == "__main__":
    import sys
    if sys.stdin.isatty():
        print("Use: cat arquivo.txt | python limpeza_texto.py > texto_limpo.md")
    else:
        bruto = sys.stdin.read()
        print(limpar_para_markdown(bruto))
