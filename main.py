#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrator de PDF Jurídico - Versão 5.0
Sistema avançado com PyMuPDF4LLM e hierarquia de conteúdo
"""

import re
import sys
import toml
import pymupdf4llm
from pathlib import Path
from typing import Dict, Tuple, List


class ProcessadorPDFJuridico:
    """Processa PDFs jurídicos com hierarquia e limpeza avançada."""
    
    def __init__(self, arquivo_limpeza: str = "limpeza.toml", 
                 arquivo_hierarquia: str = "hierarquia.toml"):
        """Inicializa o processador com dois arquivos de configuração."""
        self.arquivo_limpeza = arquivo_limpeza
        self.arquivo_hierarquia = arquivo_hierarquia
        
        self.padroes_limpeza = self._carregar_padroes(arquivo_limpeza)
        self.padroes_hierarquia = self._carregar_padroes(arquivo_hierarquia)
        
        self.config_limpeza = self.padroes_limpeza.get("configuracoes", {})
        self.config_hierarquia = self.padroes_hierarquia.get("configuracoes", {})
        
    def _carregar_padroes(self, arquivo: str) -> Dict:
        """Carrega padrões de um arquivo TOML."""
        try:
            if not Path(arquivo).exists():
                print(f"⚠️  Arquivo {arquivo} não encontrado!")
                return {}
            
            with open(arquivo, 'r', encoding='utf-8') as f:
                padroes = toml.load(f)
                versao = padroes.get('version', 'N/A')
                print(f"✅ {Path(arquivo).name} carregado: v{versao}")
                return padroes
        except Exception as e:
            print(f"❌ Erro ao carregar {arquivo}: {e}")
            return {}
    
    def extrair_metadados(self, texto: str) -> Dict:
        """Extrai metadados importantes antes de removê-los."""
        metadados = {}
        
        # Extrai número de movimentação
        match_mov = re.search(r'Movimenta[cç][aã]o?\s+(\d+)\s*:\s*([^\n]+)', texto, re.IGNORECASE)
        if match_mov:
            metadados['movimentacao_numero'] = match_mov.group(1)
            metadados['movimentacao_tipo'] = match_mov.group(2).strip()
        
        # Extrai número do processo
        match_proc = re.search(r'Processo:\s*([\d\.-]+)', texto)
        if match_proc:
            metadados['processo'] = match_proc.group(1)
        
        return metadados
    
    def extrair_texto_pymupdf(self, arquivo_pdf: str) -> Tuple[str, List[Dict]]:
        """
        Extrai texto usando PyMuPDF4LLM preservando estrutura.
        
        Returns:
            Tupla (markdown_completo, lista_metadados_por_pagina)
        """
        try:
            print(f"📄 Extraindo com PyMuPDF4LLM...")
            
            # Extrai markdown de todas as páginas
            md_texto = pymupdf4llm.to_markdown(arquivo_pdf)
            
            # Divide por páginas manualmente
            import pymupdf
            doc = pymupdf.open(arquivo_pdf)
            total_paginas = len(doc)
            
            print(f"   ✓ {total_paginas} página(s) encontradas")
            
            metadados_paginas = []
            paginas_md = []
            
            for i in range(total_paginas):
                # Extrai markdown de cada página individualmente
                md_pagina = pymupdf4llm.to_markdown(arquivo_pdf, pages=[i])
                
                # Extrai metadados desta página
                metadados = self.extrair_metadados(md_pagina)
                metadados['pagina_arquivo'] = i + 1
                metadados_paginas.append(metadados)
                
                # Adiciona marcador de página
                paginas_md.append(f"\n--- Página {i + 1} ---\n")
                paginas_md.append(md_pagina)
                
                print(f"   ✓ Página {i + 1}/{total_paginas} ({len(md_pagina)} chars)")
                
                # Mostra metadados extraídos
                if 'movimentacao_numero' in metadados:
                    print(f"      → Movimentação {metadados['movimentacao_numero']}: {metadados.get('movimentacao_tipo', '')}")
            
            doc.close()
            texto_completo = "".join(paginas_md)
            
            return texto_completo, metadados_paginas
            
        except Exception as e:
            print(f"❌ Erro ao extrair com PyMuPDF4LLM: {e}")
            print("   Tentando fallback para extração simples...")
            return self._extrair_fallback(arquivo_pdf)
    
    def _extrair_fallback(self, arquivo_pdf: str) -> Tuple[str, List[Dict]]:
        """Fallback usando PyMuPDF simples."""
        try:
            import pymupdf
            doc = pymupdf.open(arquivo_pdf)
            
            texto_completo = []
            metadados_paginas = []
            
            for i, page in enumerate(doc):
                texto = page.get_text()
                metadados = self.extrair_metadados(texto)
                metadados['pagina_arquivo'] = i + 1
                metadados_paginas.append(metadados)
                
                texto_completo.append(f"\n--- Página {i + 1} ---\n")
                texto_completo.append(texto)
            
            doc.close()
            return "".join(texto_completo), metadados_paginas
            
        except Exception as e:
            print(f"❌ Erro no fallback: {e}")
            return "", []
    
    def aplicar_hierarquia(self, texto: str) -> str:
        """Aplica hierarquia de cabeçalhos ao texto."""
        if not self.config_hierarquia.get("aplicar_hierarquia", True):
            return texto
        
        print("📐 Aplicando hierarquia de cabeçalhos...")
        
        # Processa H1
        h1_patterns = self.padroes_hierarquia.get("header_config", {}).get("h1", {}).get("patterns", [])
        for pattern in h1_patterns:
            texto = re.sub(
                f"^{re.escape(pattern)}$",
                f"# {pattern}",
                texto,
                flags=re.MULTILINE
            )
        
        # Processa H2
        h2_patterns = self.padroes_hierarquia.get("header_config", {}).get("h2", {}).get("patterns", [])
        for pattern in h2_patterns:
            # Se começa com ^, é regex
            if pattern.startswith("^"):
                texto = re.sub(
                    pattern + "$",
                    lambda m: f"## {m.group(0)}",
                    texto,
                    flags=re.MULTILINE
                )
            else:
                texto = re.sub(
                    f"^{re.escape(pattern)}$",
                    f"## {pattern}",
                    texto,
                    flags=re.MULTILINE
                )
        
        # Processa H3
        h3_patterns = self.padroes_hierarquia.get("header_config", {}).get("h3", {}).get("patterns", [])
        for pattern in h3_patterns:
            if pattern.startswith("^"):
                texto = re.sub(
                    pattern + "$",
                    lambda m: f"### {m.group(0)}",
                    texto,
                    flags=re.MULTILINE
                )
            else:
                texto = re.sub(
                    f"^{re.escape(pattern)}$",
                    f"### {pattern}",
                    texto,
                    flags=re.MULTILINE
                )
        
        print("   ✓ Hierarquia aplicada")
        return texto
    
    def preservar_conteudo_importante(self, texto: str) -> Tuple[str, List[str]]:
        """
        Marca conteúdo importante para preservação durante a limpeza.
        
        Returns:
            Tupla (texto_com_marcadores, lista_de_conteudos_preservados)
        """
        padroes_preservar = self.padroes_hierarquia.get("padroes_preservar", {}).get("patterns", [])
        
        if not padroes_preservar:
            return texto, []
        
        print("🔒 Protegendo conteúdo importante...")
        
        conteudos_preservados = []
        
        for i, padrao in enumerate(padroes_preservar):
            try:
                matches = re.findall(padrao, texto, flags=re.MULTILINE | re.IGNORECASE)
                if matches:
                    for match in matches:
                        placeholder = f"___PRESERVADO_{i}_{len(conteudos_preservados)}___"
                        conteudos_preservados.append(str(match))
                        texto = texto.replace(str(match), placeholder, 1)
            except:
                pass
        
        print(f"   ✓ {len(conteudos_preservados)} blocos protegidos")
        return texto, conteudos_preservados
    
    def restaurar_conteudo_preservado(self, texto: str, conteudos: List[str]) -> str:
        """Restaura conteúdo que foi preservado."""
        for i, conteudo in enumerate(conteudos):
            for j in range(len(conteudos)):
                placeholder = f"___PRESERVADO_{i}_{j}___"
                if placeholder in texto:
                    texto = texto.replace(placeholder, conteudo, 1)
                    break
        
        return texto
    
    def separar_por_paginas(self, texto: str) -> List[Tuple[int, str]]:
        """Separa o texto em páginas individuais."""
        paginas = []
        partes = re.split(r'---\s*Página\s+(\d+)\s*---\s*\n?', texto)
        
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
        padroes = self.padroes_limpeza.get(secao, {}).get("patterns", [])
        
        if not padroes:
            return texto, 0
        
        removidos = 0
        
        for padrao in padroes:
            try:
                matches = re.findall(padrao, texto, flags=re.MULTILINE | re.IGNORECASE)
                if matches:
                    removidos += len(matches)
                
                texto = re.sub(padrao, "", texto, flags=re.MULTILINE | re.IGNORECASE)
            except:
                pass
        
        return texto, removidos
    
    def remover_ruidos(self, texto: str) -> str:
        """Remove todos os padrões de ruído."""
        ordem = self.config_limpeza.get("ordem_processamento", [
            "metadados_processuais",
            "assinaturas_digitais",
            "cabecalhos_institucionais",
            "textos_margem_rotacionados",
            "rodape_institucional",
            "rodape_links",
            "paginacao",
            "separadores"
        ])
        
        for secao in ordem:
            texto, removidos = self.remover_padroes_secao(texto, secao)
        
        return texto
    
    def limpar_fragmentos_finais(self, texto: str) -> str:
        """Remove fragmentos residuais."""
        linhas_limpas = []
        
        for linha in texto.split('\n'):
            linha_strip = linha.strip()
            
            if not linha_strip:
                linhas_limpas.append(linha)
                continue
            
            # Remove linhas problemáticas
            if re.search(r'\d{15,}', linha_strip):
                continue
            if re.match(r'^\s*:\s*\d{5,}', linha_strip):
                continue
            if re.search(r'no\s+endere', linha_strip, re.IGNORECASE):
                continue
            if len(linha_strip) < 5 and re.match(r'^[:\s,\-_]+$', linha_strip):
                continue
            
            linhas_limpas.append(linha)
        
        return '\n'.join(linhas_limpas)
    
    def normalizar_espacos(self, texto: str) -> str:
        """Normaliza espaçamento."""
        texto = re.sub(r' {2,}', ' ', texto)
        linhas = [linha.rstrip() for linha in texto.split('\n')]
        
        # Remove linhas vazias excessivas
        max_vazias = self.config_limpeza.get("max_linhas_vazias_consecutivas", 1)
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
        min_tam = self.config_limpeza.get("min_tamanho_linha_util", 2)
        linhas_finais = []
        
        for linha in linhas_filtradas:
            if len(linha.strip()) >= min_tam or linha.strip() == '':
                if re.search(r'[a-zA-ZÀ-ÿ#*-]', linha) or linha.strip() == '':
                    linhas_finais.append(linha)
        
        return '\n'.join(linhas_finais).strip()
    
    def montar_documento_final(self, paginas_limpas: List[Tuple[int, str]], 
                              metadados_paginas: List[Dict]) -> str:
        """Monta o documento final com cabeçalhos de página."""
        partes = []
        total_paginas = len(paginas_limpas)
        
        for idx, (numero_pagina, conteudo) in enumerate(paginas_limpas):
            # Busca metadados desta página
            metadados = None
            for meta in metadados_paginas:
                if meta.get('pagina_arquivo') == numero_pagina:
                    metadados = meta
                    break
            
            # Adiciona cabeçalho apenas se houver mais de 1 página
            if total_paginas > 1:
                movimentacao = ""
                if metadados and 'movimentacao_numero' in metadados:
                    mov_num = metadados['movimentacao_numero']
                    mov_tipo = metadados.get('movimentacao_tipo', '')
                    movimentacao = f" | MOVIMENTAÇÃO {mov_num}"
                    if mov_tipo:
                        movimentacao += f" ({mov_tipo})"
                
                if idx > 0:
                    partes.append("")
                
                partes.append(f"{'='*60}")
                partes.append(f"PÁGINA {numero_pagina}{movimentacao}")
                partes.append(f"{'='*60}")
                partes.append("")
            
            partes.append(conteudo)
        
        return '\n'.join(partes).strip()
    
    def processar(self, arquivo_pdf: str, arquivo_txt: str, arquivo_md: str) -> Tuple[str, str]:
        """Processa o PDF completo."""
        print("\n" + "="*70)
        print("🔍 PROCESSAMENTO DE PDF JURÍDICO v5.0 - PyMuPDF4LLM")
        print("="*70)
        
        if not self.padroes_limpeza:
            print("❌ Padrões de limpeza não carregados!")
            return "", ""
        
        # Etapa 1: Extração com PyMuPDF4LLM
        print("\n" + "="*70)
        print("📖 ETAPA 1: Extração com PyMuPDF4LLM")
        print("="*70)
        texto_bruto, metadados_paginas = self.extrair_texto_pymupdf(arquivo_pdf)
        
        if not texto_bruto:
            return "", ""
        
        # Salva texto bruto
        with open(arquivo_txt, 'w', encoding='utf-8') as f:
            f.write(texto_bruto)
        print(f"\n💾 Salvo: {arquivo_txt} ({len(texto_bruto):,} chars)")
        
        # Etapa 2: Aplicar hierarquia
        print("\n" + "="*70)
        print("📐 ETAPA 2: Aplicação de Hierarquia")
        print("="*70)
        texto = self.aplicar_hierarquia(texto_bruto)
        
        # Determina se deve preservar primeira página
        total_paginas = len(metadados_paginas)
        preservar_capa = total_paginas > 1
        
        if preservar_capa:
            print(f"\n   📋 Documento com {total_paginas} páginas")
            print("   ℹ️  A primeira página (capa) será preservada intacta")
        
        # Etapa 3: Separar páginas ANTES de limpar
        print("\n" + "="*70)
        print("📑 ETAPA 3: Separação por páginas")
        print("="*70)
        
        marcadores = re.findall(r'---\s*Página\s+\d+\s*---', texto)
        print(f"   🔍 Marcadores encontrados: {len(marcadores)}")
        
        paginas_texto = self.separar_por_paginas(texto)
        print(f"   ✓ {len(paginas_texto)} página(s) separada(s)")
        
        # Etapa 4: Limpar cada página
        print("\n" + "="*70)
        print("🧹 ETAPA 4: Limpeza por página")
        print("="*70)
        
        paginas_limpas = []
        for num_pag, conteudo_pag in paginas_texto:
            print(f"\n   Processando página {num_pag}...")
            
            if preservar_capa and num_pag == 1:
                print("      Página preservada (capa do processo)")
                conteudo_limpo = conteudo_pag
            else:
                # Preserva conteúdo importante
                conteudo_protegido, preservados = self.preservar_conteudo_importante(conteudo_pag)
                
                # Remove ruídos
                conteudo_limpo = self.remover_ruidos(conteudo_protegido)
                conteudo_limpo = self.limpar_fragmentos_finais(conteudo_limpo)
                
                # Restaura conteúdo preservado
                conteudo_limpo = self.restaurar_conteudo_preservado(conteudo_limpo, preservados)
            
            # Normaliza
            conteudo_final = self.normalizar_espacos(conteudo_limpo)
            
            # Sempre adiciona a página, mesmo se vazia
            if conteudo_final:
                paginas_limpas.append((num_pag, conteudo_final))
                print(f"      {len(conteudo_final)} chars finais")
            else:
                paginas_limpas.append((num_pag, "*Página sem conteúdo após limpeza*"))
                print(f"      Página vazia após limpeza")
        
        # Etapa 5: Montar documento
        print("\n" + "="*70)
        print("📄 ETAPA 5: Montagem do documento")
        print("="*70)
        texto_final = self.montar_documento_final(paginas_limpas, metadados_paginas)
        print(f"   Documento montado com {len(paginas_limpas)} página(s)")
        
        # Estatísticas
        print("\n" + "="*70)
        print("📊 ESTATÍSTICAS")
        print("="*70)
        
        palavras = len(texto_final.split())
        linhas = len([l for l in texto_final.split('\n') if l.strip()])
        reducao = len(texto_bruto) - len(texto_final)
        percentual = (reducao / len(texto_bruto) * 100) if texto_bruto else 0
        
        print(f"   Original: {len(texto_bruto):,} chars")
        print(f"   Removido: {reducao:,} chars ({percentual:.1f}%)")
        print(f"   Final: {len(texto_final):,} chars")
        print(f"   Linhas: {linhas}")
        print(f"   Palavras: {palavras}")
        
        # Salva resultado
        with open(arquivo_md, 'w', encoding='utf-8') as f:
            if texto_final:
                f.write(texto_final)
            else:
                f.write("*Documento sem conteúdo útil.*\n")
        
        print(f"\n💾 Salvo: {arquivo_md}")
        
        print("\n" + "="*70)
        if palavras > 0:
            print("✅ PROCESSAMENTO CONCLUÍDO!")
        else:
            print("⚠️  DOCUMENTO SEM CONTEÚDO ÚTIL")
        print("="*70 + "\n")
        
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
    processador = ProcessadorPDFJuridico("limpeza.toml", "hierarquia.toml")
    texto_bruto, texto_limpo = processador.processar(
        arquivo_pdf=arquivo_pdf,
        arquivo_txt=str(arquivo_txt),
        arquivo_md=str(arquivo_md)
    )
    
    if texto_limpo:
        print(f"✅ {len(texto_limpo.split())} palavras no documento final")


if __name__ == "__main__":
    main()