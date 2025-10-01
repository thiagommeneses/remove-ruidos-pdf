#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrator de PDF Jurídico com Remoção de Ruídos - Versão 4.2
Sistema robusto de limpeza de metadados processuais
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import PyPDF2
import toml


class ProcessadorPDFJuridico:
    """Processa PDFs jurídicos removendo metadados e ruídos institucionais."""

    def __init__(self, arquivo_padroes: str = "limpeza.toml"):
        """Inicializa o processador."""
        self.arquivo_padroes = arquivo_padroes
        self.padroes = self._carregar_padroes(arquivo_padroes)
        self.config = self.padroes.get("configuracoes", {})

    def _carregar_padroes(self, arquivo: str) -> Dict:
        """Carrega os padrões do arquivo TOML."""
        try:
            if not Path(arquivo).exists():
                print(f"⚠️  Arquivo {arquivo} não encontrado!")
                return {}

            with open(arquivo, "r", encoding="utf-8") as f:
                padroes = toml.load(f)
                print(f"✅ Padrões carregados: v{padroes.get('version', 'N/A')}")
                return padroes
        except Exception as e:
            print(f"❌ Erro ao carregar padrões: {e}")
            return {}

    def extrair_metadados(self, texto: str) -> Dict:
        """Extrai metadados importantes antes de removê-los."""
        metadados = {}

        # Extrai número de movimentação
        match_mov = re.search(
            r"Movimenta[cç][aã]o?\s+(\d+)\s*:\s*(\w+)", texto, re.IGNORECASE
        )
        if match_mov:
            metadados["movimentacao_numero"] = match_mov.group(1)
            metadados["movimentacao_tipo"] = match_mov.group(2)

        # Extrai número do processo
        match_proc = re.search(r"Processo:\s*([\d\.-]+)", texto)
        if match_proc:
            metadados["processo"] = match_proc.group(1)

        return metadados

    def extrair_texto_pdf(self, arquivo_pdf: str) -> Tuple[str, List[Dict]]:
        """Extrai o texto de um arquivo PDF e metadados."""
        texto_completo = []
        metadados_paginas = []

        try:
            with open(arquivo_pdf, "rb") as f:
                leitor = PyPDF2.PdfReader(f)
                total_paginas = len(leitor.pages)

                print(f"📄 Extraindo texto de {total_paginas} página(s)...")

                for i, pagina in enumerate(leitor.pages, 1):
                    texto = pagina.extract_text()
                    if texto:
                        # Extrai metadados desta página
                        metadados = self.extrair_metadados(texto)
                        metadados["pagina_arquivo"] = i
                        metadados_paginas.append(metadados)

                        # Adiciona marcador de página
                        texto_completo.append(f"\n--- Página {i} ---\n")
                        texto_completo.append(texto)
                        print(f"   ✓ Página {i}/{total_paginas} ({len(texto)} chars)")

                        # Mostra metadados extraídos
                        if "movimentacao_numero" in metadados:
                            mov_num = metadados['movimentacao_numero']
                            mov_tipo = metadados.get('movimentacao_tipo', '')
                            print(f"      → Movimentação {mov_num}: {mov_tipo}")

                texto_str = "".join(texto_completo)
                return texto_str, metadados_paginas

        except Exception as e:
            print(f"❌ Erro ao extrair texto: {e}")
            return "", []

    def adicionar_quebras_linha(self, texto: str) -> str:
        """Adiciona quebras de linha estratégicas."""
        texto = re.sub(r"([a-z\)])([A-Z]{3,})", r"\1\n\2", texto)
        texto = re.sub(r"([^\n])(Usuário:)", r"\1\n\2", texto)
        texto = re.sub(r"([^\n])(Processo:)", r"\1\n\2", texto)
        texto = re.sub(r"([^\n])(Tribunal\s+de)", r"\1\n\2", texto)
        texto = re.sub(r"([^\n])(Documento\s+Assinado)", r"\1\n\2", texto)
        texto = re.sub(r"([^\n])(PROCESSO\s+CRIMINAL)", r"\1\n\2", texto)
        texto = re.sub(r"([^\n])(https?://)", r"\1\n\2", texto)
        texto = re.sub(r"(\d{2}:\d{2}:\d{2})([A-Z])", r"\1\n\2", texto)

        return texto

    def separar_por_paginas(self, texto: str) -> List[Tuple[int, str]]:
        """Separa o texto em páginas individuais."""
        paginas = []

        # Divide pelo marcador de página
        partes = re.split(r"---\s*Página\s+(\d+)\s*---\s*\n?", texto)

        # partes[0] é vazio, partes[1]=num, partes[2]=conteudo, ...
        i = 1
        while i < len(partes):
            if i + 1 < len(partes):
                numero_pagina = int(partes[i])
                conteudo = partes[i + 1].strip()
                if conteudo:
                    paginas.append((numero_pagina, conteudo))
                    print(f"      • Página {numero_pagina}: {len(conteudo)} chars")
                i += 2
            else:
                break

        return paginas

    def remover_padroes_secao(self, texto: str, secao: str) -> Tuple[str, int]:
        """Remove padrões de uma seção específica."""
        padroes = self.padroes.get(secao, {}).get("patterns", [])

        if not padroes:
            return texto, 0

        removidos = 0

        for padrao in padroes:
            try:
                matches = re.findall(padrao, texto, flags=re.MULTILINE | re.IGNORECASE)
                if matches:
                    removidos += len(matches)

                texto = re.sub(padrao, "", texto, flags=re.MULTILINE | re.IGNORECASE)
            except re.error:
                # Ignora padrões regex inválidos
                pass

        return texto, removidos

    def remover_ruidos(self, texto: str) -> str:
        """Remove todos os padrões de ruído."""
        ordem = self.config.get(
            "ordem_processamento",
            [
                "metadados_processuais",
                "assinaturas_digitais",
                "cabecalhos_institucionais",
                "rodape_links",
                "paginacao",
                "separadores",
            ],
        )

        for secao in ordem:
            texto, _ = self.remover_padroes_secao(texto, secao)

        return texto

    def limpar_fragmentos_finais(self, texto: str) -> str:
        """Remove fragmentos residuais linha por linha."""
        linhas_limpas = []

        for linha in texto.split("\n"):
            linha_strip = linha.strip()

            if not linha_strip:
                linhas_limpas.append(linha)
                continue

            # Remove linhas problemáticas
            if re.search(r"\d{15,}", linha_strip):
                continue
            if re.match(r"^\s*:\s*\d{5,}", linha_strip):
                continue
            if re.search(r"no\s+endere", linha_strip, re.IGNORECASE):
                continue
            if len(linha_strip) < 5 and re.match(r"^[:\s,\-_]+$", linha_strip):
                continue

            linhas_limpas.append(linha)

        return "\n".join(linhas_limpas)

    def normalizar_espacos(self, texto: str) -> str:
        """Normaliza espaçamento."""
        texto = re.sub(r" {2,}", " ", texto)
        linhas = [linha.strip() for linha in texto.split("\n")]

        # Remove linhas vazias excessivas
        max_vazias = self.config.get("max_linhas_vazias_consecutivas", 1)
        linhas_filtradas = []
        vazias = 0

        for linha in linhas:
            if linha:
                linhas_filtradas.append(linha)
                vazias = 0
            else:
                vazias += 1
                if vazias <= max_vazias:
                    linhas_filtradas.append(linha)

        # Remove linhas muito curtas
        min_tam = self.config.get("min_tamanho_linha_util", 2)
        linhas_finais = []

        for linha in linhas_filtradas:
            if len(linha.strip()) >= min_tam or linha.strip() == "":
                if re.search(r"[a-zA-ZÀ-ÿ]", linha) or linha.strip() == "":
                    linhas_finais.append(linha)

        return "\n".join(linhas_finais).strip()

    def montar_documento_final(
        self, paginas_limpas: List[Tuple[int, str]], metadados_paginas: List[Dict]
    ) -> str:
        """Monta o documento final com cabeçalhos de página."""
        partes = []
        total_paginas = len(paginas_limpas)

        for idx, (numero_pagina, conteudo) in enumerate(paginas_limpas):
            # Busca metadados desta página
            metadados = None
            for meta in metadados_paginas:
                if meta.get("pagina_arquivo") == numero_pagina:
                    metadados = meta
                    break

            # Adiciona cabeçalho apenas se houver mais de 1 página
            if total_paginas > 1:
                # Monta informação de movimentação (só se existir)
                movimentacao = ""
                if metadados and "movimentacao_numero" in metadados:
                    mov_num = metadados["movimentacao_numero"]
                    mov_tipo = metadados.get("movimentacao_tipo", "")
                    movimentacao = f" | MOVIMENTAÇÃO {mov_num}"
                    if mov_tipo:
                        movimentacao += f" ({mov_tipo})"

                # Adiciona separador antes (exceto na primeira página)
                if idx > 0:
                    partes.append("")

                partes.append(f"{'='*60}")
                partes.append(f"PÁGINA {numero_pagina}{movimentacao}")
                partes.append(f"{'='*60}")
                partes.append("")

            # Adiciona o conteúdo
            partes.append(conteudo)

        return "\n".join(partes).strip()

    def processar(
        self, arquivo_pdf: str, arquivo_txt: str, arquivo_md: str
    ) -> Tuple[str, str]:
        """Processa o PDF completo."""
        print("\n" + "=" * 70)
        print("🔍 PROCESSAMENTO DE PDF JURÍDICO v4.2")
        print("=" * 70)

        if not self.padroes:
            print("❌ Nenhum padrão de limpeza carregado!")
            return "", ""

        # Etapa 1: Extração
        print("\n" + "=" * 70)
        print("📖 ETAPA 1: Extração")
        print("=" * 70)
        texto_bruto, metadados_paginas = self.extrair_texto_pdf(arquivo_pdf)

        if not texto_bruto:
            return "", ""

        with open(arquivo_txt, "w", encoding="utf-8") as f:
            f.write(texto_bruto)
        print(f"\n💾 Salvo: {arquivo_txt} ({len(texto_bruto):,} chars)")

        # Etapa 2: Quebras de linha
        print("\n" + "=" * 70)
        print("🔧 ETAPA 2: Normalização de quebras")
        print("=" * 70)
        texto = self.adicionar_quebras_linha(texto_bruto)
        print("   ✓ Quebras de linha adicionadas")

        # Determina se deve preservar primeira página
        total_paginas = len(metadados_paginas)
        preservar_capa = total_paginas > 1

        if preservar_capa:
            print(f"\n   📋 Documento com {total_paginas} páginas")
            print("   ℹ️  A primeira página (capa) será preservada intacta")

        # Etapa 3: Separar páginas ANTES de limpar
        print("\n" + "=" * 70)
        print("📑 ETAPA 3: Separação por páginas")
        print("=" * 70)

        marcadores = re.findall(r"---\s*Página\s+\d+\s*---", texto)
        print(f"   🔍 Marcadores encontrados: {len(marcadores)}")

        paginas_texto = self.separar_por_paginas(texto)
        print(f"   ✓ {len(paginas_texto)} página(s) separada(s)")

        # Etapa 4: Limpar cada página
        print("\n" + "=" * 70)
        print("🧹 ETAPA 4: Remoção de metadados por página")
        print("=" * 70)

        paginas_limpas = []
        for num_pag, conteudo_pag in paginas_texto:
            print(f"\n   📄 Processando página {num_pag}...")

            if preservar_capa and num_pag == 1:
                print("      ⚠️  Página preservada (capa do processo)")
                conteudo_limpo = conteudo_pag
            else:
                conteudo_limpo = self.remover_ruidos(conteudo_pag)
                conteudo_limpo = self.limpar_fragmentos_finais(conteudo_limpo)

            conteudo_final = self.normalizar_espacos(conteudo_limpo)

            # Sempre adiciona a página, mesmo se vazia
            if conteudo_final:
                paginas_limpas.append((num_pag, conteudo_final))
                print(f"      ✓ {len(conteudo_final)} chars finais")
            else:
                paginas_limpas.append((num_pag, "*Página sem conteúdo após limpeza*"))
                print("      ⚠️  Página vazia após limpeza")

        # Etapa 5: Montar documento
        print("\n" + "=" * 70)
        print("📄 ETAPA 5: Montagem do documento")
        print("=" * 70)
        texto_final = self.montar_documento_final(paginas_limpas, metadados_paginas)
        print(f"   ✓ Documento montado com {len(paginas_limpas)} página(s)")

        # Estatísticas
        print("\n" + "=" * 70)
        print("📊 ESTATÍSTICAS")
        print("=" * 70)

        palavras = len(texto_final.split())
        linhas = len([linha for linha in texto_final.split("\n") if linha.strip()])
        reducao = len(texto_bruto) - len(texto_final)
        percentual = (reducao / len(texto_bruto) * 100) if texto_bruto else 0

        print(f"   • Original: {len(texto_bruto):,} chars")
        print(f"   • Removido: {reducao:,} chars ({percentual:.1f}%)")
        print(f"   • Final: {len(texto_final):,} chars")
        print(f"   • Linhas: {linhas}")
        print(f"   • Palavras: {palavras}")

        # Salva resultado
        with open(arquivo_md, "w", encoding="utf-8") as f:
            if texto_final:
                f.write(texto_final)
            else:
                f.write("*Documento sem conteúdo útil.*\n")

        print(f"\n💾 Salvo: {arquivo_md}")

        print("\n" + "=" * 70)
        if palavras > 0:
            print("✅ PROCESSAMENTO CONCLUÍDO!")
        else:
            print("⚠️  DOCUMENTO SEM CONTEÚDO ÚTIL")
        print("=" * 70 + "\n")

        return texto_bruto, texto_final


def main():
    """Função principal."""
    if len(sys.argv) < 2:
        print("❌ Uso incorreto!")
        print(f"💡 Uso: python {sys.argv[0]} <arquivo.pdf>")
        print(f"   Exemplo: python {sys.argv[0]} IP1.pdf")
        return

    arquivo_pdf = sys.argv[1]

    if not Path(arquivo_pdf).exists():
        print(f"❌ Arquivo não encontrado: {arquivo_pdf}")
        return

    # Gera nomes de saída
    caminho = Path(arquivo_pdf)
    nome_base = caminho.stem
    diretorio = caminho.parent

    arquivo_txt = diretorio / f"{nome_base}_texto-extraido.txt"
    arquivo_md = diretorio / f"{nome_base}_texto-limpo.md"

    print(f"📁 Entrada: {arquivo_pdf}")
    print(f"📄 Saída 1: {arquivo_txt}")
    print(f"📄 Saída 2: {arquivo_md}")

    # Processa
    processador = ProcessadorPDFJuridico("limpeza.toml")
    _, texto_limpo = processador.processar(
        arquivo_pdf=arquivo_pdf,
        arquivo_txt=str(arquivo_txt),
        arquivo_md=str(arquivo_md),
    )

    if texto_limpo:
        print(f"✅ {len(texto_limpo.split())} palavras no documento final")


if __name__ == "__main__":
    main()
