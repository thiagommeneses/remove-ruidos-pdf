#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limpar_ocr_suave.py — limpeza mínima de texto OCR.

Mantém a estrutura original (inclusive divisões de páginas),
apenas corrige caracteres estranhos e normaliza texto.
"""

import re
import unicodedata
import argparse

def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)

def remove_noise(text: str) -> str:
    lines = []
    for line in text.splitlines():
        # remove sequências de lixo (só símbolos repetidos)
        if re.fullmatch(r"[;:|qoa-zA-Z]{0,3}\s*(Tp|Ta|bo|Ea|na RR su|q ooo|ae Ess o)?", line.strip(), re.IGNORECASE):
            continue
        # remove linhas só de símbolos
        if re.fullmatch(r"[!@#$%^&*()_+=\-\[\]{}|\\:;\"'<>,.?/~`]+", line.strip()):
            continue
        # compacta espaços múltiplos
        line = re.sub(r"[ \t]{2,}", " ", line)
        lines.append(line)
    return "\n".join(lines)

def clean_ocr_text_soft(text: str) -> str:
    t = normalize_unicode(text)
    t = remove_noise(t)
    return t.strip() + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="Arquivo de entrada OCR (.txt/.md)")
    ap.add_argument("-o", "--output", required=True, help="Arquivo de saída limpo (.md)")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        raw = f.read()
    cleaned = clean_ocr_text_soft(raw)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(cleaned)

if __name__ == "__main__":
    main()
