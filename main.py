#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrator de PDF Jurídico - Versão 5.1
Sistema avançado com PyMuPDF4LLM, OCR otimizado e hierarquia de conteúdo
"""
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import pymupdf4llm
import pymupdf
import toml

# Imports opcionais para OCR
try:
    import pytesseract
    from PIL import Image
    import numpy as np
    OCR_DISPONIVEL = True
except ImportError:
    OCR_DISPONIVEL = False
    print("⚠️  OCR não disponível. Instale: pip install pytesseract Pillow numpy")


class ProcessadorPDFJuridico:
    """Processa PDFs jurídicos com hierarquia e limpeza avançada."""
    
    def __init__(
        self,
        arquivo_limpeza: str = "limpeza.toml",
        arquivo_hierarquia: str = "hierarquia.toml",
        usar_ocr: bool = True,
    ):
        """Inicializa o processador com dois arquivos de configuração."""
        self.arquivo_limpeza = arquivo_limpeza
        self.arquivo_hierarquia = arquivo_hierarquia
        self.usar_ocr = usar_ocr and OCR_DISPONIVEL
        
        self.padroes_limpeza = self._carregar_padroes(arquivo_limpeza)
        self.padroes_hierarquia = self._carregar_padroes(arquivo_hierarquia)
        
        self.config_limpeza = self.padroes_limpeza.get("configuracoes", {})
        self.config_hierarquia = self.padroes_hierarquia.get("configuracoes", {})
        
        if self.usar_ocr:
            # Configuração otimizada do Tesseract (modo mais rápido)
            self.tesseract_config = '--psm 6 --oem 3'  # PSM 6 = bloco uniforme, OEM 3 = modo padrão
    
    def _carregar_padroes(self, arquivo: str) -> Dict:
        """Carrega padrões de um arquivo TOML."""
        try:
            if not Path(arquivo).exists():
                print(f"Arquivo {arquivo} não encontrado!")
                return {}
            
            with open(arquivo, "r", encoding="utf-8") as f:
                padroes = toml.load(f)
                versao = padroes.get("version", "N/A")
                print(f"✓ {Path(arquivo).name} carregado: v{versao}")
                return padroes
        except Exception as e:
            print(f"Erro ao carregar {arquivo}: {e}")
            return {}
    
    def _detectar_tipo_pagina(self, page) -> str:
        """
        Detecta se página contém texto extraível ou é imagem escaneada.
        
        Returns:
            'texto', 'imagem' ou 'hibrida'
        """
        texto = page.get_text()
        images = page.get_images()
        
        # Se não tem imagens, é puramente texto
        if len(images) == 0:
            return 'texto'
        
        # Calcula área total das imagens vs área da página
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height
        
        total_image_area = 0
        for img_info in images:
            try:
                xref = img_info[0]
                img_rect = page.get_image_bbox(img_info)
                if img_rect:
                    img_area = abs(img_rect.width * img_rect.height)
                    total_image_area += img_area
            except:
                continue
        
        # Se imagens ocupam mais de 30% da página, considerar híbrida/imagem
        if page_area > 0:
            image_ratio = total_image_area / page_area
            
            # Imagens grandes indicam conteúdo escaneado
            if image_ratio > 0.3:
                # Se tem muito texto (> 500 chars), é híbrida mas precisa OCR
                if len(texto.strip()) > 500:
                    return 'hibrida'
                else:
                    return 'imagem'
        
        # Pouco texto + imagens = escaneado
        if len(texto.strip()) < 100 and len(images) > 0:
            return 'imagem'
        
        return 'texto'
    
    def _preprocessar_imagem(self, img: Image.Image) -> Image.Image:
        """
        Pré-processa imagem para melhorar OCR.
        Rápido e eficiente para documentos jurídicos.
        """
        # Converte para escala de cinza
        img = img.convert('L')
        
        # Aumenta contraste (melhora OCR em ~15%)
        img_array = np.array(img)
        img_array = np.clip(img_array * 1.2, 0, 255).astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def _extrair_texto_ocr_pagina(self, page, page_num: int) -> str:
        """
        Extrai texto de uma página usando OCR otimizado.
        Tempo alvo: < 800ms por página.
        """
        try:
            # Renderiza página em imagem (resolução otimizada para velocidade)
            pix = page.get_pixmap(dpi=200)  # 200 DPI = bom equilíbrio velocidade/qualidade
            
            # Converte para PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Pré-processa
            img = self._preprocessar_imagem(img)
            
            # OCR com Tesseract otimizado
            texto_ocr = pytesseract.image_to_string(
                img,
                lang='por',
                config=self.tesseract_config
            )
            
            # Para páginas híbridas, pode combinar com texto extraível se útil
            # mas geralmente o OCR substitui completamente
            return texto_ocr.strip()
            
        except Exception as e:
            print(f"      ⚠️  Erro no OCR da página {page_num}: {e}")
            # Fallback: tenta extrair texto normal
            try:
                return page.get_text()
            except:
                return ""
    
    def extrair_metadados(self, texto: str) -> Dict:
        """Extrai metadados importantes antes de removê-los."""
        metadados = {}
        
        match_mov = re.search(
            r"Movimenta[cç][aã]o?\s+(\d+)\s*:\s*([^\n]+)", texto, re.IGNORECASE
        )
        if match_mov:
            metadados["movimentacao_numero"] = match_mov.group(1)
            metadados["movimentacao_tipo"] = match_mov.group(2).strip()
        
        match_proc = re.search(r"Processo:\s*([\d\.-]+)", texto)
        if match_proc:
            metadados["processo"] = match_proc.group(1)
        
        return metadados
    
    def extrair_texto_pymupdf(self, arquivo_pdf: str) -> Tuple[str, List[Dict]]:
        """Extrai texto usando PyMuPDF4LLM com OCR para páginas escaneadas."""
        try:
            print("Extraindo com PyMuPDF4LLM + OCR...")
            
            doc = pymupdf.open(arquivo_pdf)
            total_paginas = len(doc)
            
            print(f"   {total_paginas} página(s) encontradas")
            
            metadados_paginas = []
            paginas_md = []
            
            # Detecta páginas que precisam de OCR
            paginas_ocr = []
            for i in range(total_paginas):
                tipo = self._detectar_tipo_pagina(doc[i])
                if tipo in ['imagem', 'hibrida'] and self.usar_ocr:
                    paginas_ocr.append(i)
            
            if paginas_ocr:
                print(f"   {len(paginas_ocr)} página(s) necessitam OCR")
            
            # Processa páginas
            for i in range(total_paginas):
                page = doc[i]
                tipo_pagina = self._detectar_tipo_pagina(page)
                
                if tipo_pagina in ['imagem', 'hibrida'] and self.usar_ocr:
                    # Usa OCR para imagens e páginas híbridas
                    print(f"   Página {i + 1}/{total_paginas} [{tipo_pagina.upper()}+OCR]", end="")
                    import time
                    inicio = time.time()
                    
                    md_pagina = self._extrair_texto_ocr_pagina(page, i + 1)
                    
                    tempo = time.time() - inicio
                    print(f" ({tempo:.2f}s, {len(md_pagina)} chars)")
                else:
                    # Extração normal
                    md_pagina = pymupdf4llm.to_markdown(arquivo_pdf, pages=[i])
                    print(f"   Página {i + 1}/{total_paginas} [TEXTO] ({len(md_pagina)} chars)")
                
                metadados = self.extrair_metadados(md_pagina)
                metadados["pagina_arquivo"] = i + 1
                metadados["tipo_extracao"] = "ocr" if tipo_pagina in ['imagem', 'hibrida'] else "texto"
                metadados_paginas.append(metadados)
                
                paginas_md.append(f"\n--- Página {i + 1} ---\n")
                paginas_md.append(md_pagina)
                
                if "movimentacao_numero" in metadados:
                    mov_num = metadados['movimentacao_numero']
                    mov_tipo = metadados.get('movimentacao_tipo', '')
                    print(f"      → Movimentação {mov_num}: {mov_tipo}")
            
            doc.close()
            texto_completo = "".join(paginas_md)
            
            return texto_completo, metadados_paginas
            
        except Exception as e:
            print(f"Erro ao extrair com PyMuPDF4LLM: {e}")
            return self._extrair_fallback(arquivo_pdf)
    
    def _extrair_fallback(self, arquivo_pdf: str) -> Tuple[str, List[Dict]]:
        """Fallback usando PyMuPDF simples."""
        try:
            doc = pymupdf.open(arquivo_pdf)
            
            texto_completo = []
            metadados_paginas = []
            
            for i, page in enumerate(doc):
                texto = page.get_text()
                metadados = self.extrair_metadados(texto)
                metadados["pagina_arquivo"] = i + 1
                metadados["tipo_extracao"] = "fallback"
                metadados_paginas.append(metadados)
                
                texto_completo.append(f"\n--- Página {i + 1} ---\n")
                texto_completo.append(texto)
            
            doc.close()
            return "".join(texto_completo), metadados_paginas
            
        except Exception as e:
            print(f"Erro no fallback: {e}")
            return "", []
    
    def separar_por_paginas(self, texto: str) -> List[Tuple[int, str]]:
        """Separa o texto em páginas individuais."""
        paginas = []
        partes = re.split(r"---\s*Página\s+(\d+)\s*---\s*\n?", texto)
        
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
            except re.error:
                pass
        
        return texto, removidos
    
    def remover_ruidos(self, texto: str) -> str:
        """Remove todos os padrões de ruído."""
        ordem = self.config_limpeza.get(
            "ordem_processamento",
            [
                "metadados_processuais",
                "assinaturas_digitais",
                "cabecalhos_institucionais",
                "textos_margem_rotacionados",
                "rodape_institucional",
                "rodape_links",
                "paginacao",
                "separadores",
            ],
        )
        
        for secao in ordem:
            texto, _ = self.remover_padroes_secao(texto, secao)
        
        return texto
    
    def limpar_fragmentos_finais(self, texto: str) -> str:
        """Remove fragmentos residuais."""
        linhas_limpas = []
        
        for linha in texto.split("\n"):
            linha_strip = linha.strip()
            
            if not linha_strip:
                linhas_limpas.append(linha)
                continue
            
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
        """Normaliza espaçamento e remove artefatos de markdown."""
        texto = re.sub(r" {2,}", " ", texto)
        
        linhas = []
        for linha in texto.split("\n"):
            linha_strip = linha.strip()
            
            # Remove linhas só com asteriscos
            asterisco_pattern = r"^\*+$"
            if re.match(asterisco_pattern, linha_strip):
                continue
            
            # Remove linhas com asteriscos e espaços
            if len(linha_strip) < 50:
                asterisco_espaco_pattern = r"^[\s\*]+$"
                if re.match(asterisco_espaco_pattern, linha_strip):
                    continue
            
            linhas.append(linha.rstrip())
        
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
        
        min_tam = self.config_limpeza.get("min_tamanho_linha_util", 2)
        linhas_finais = []
        
        for linha in linhas_filtradas:
            if linha.strip() == "":
                linhas_finais.append(linha)
                continue
            
            markdown_pattern = r"^#{1,4}\s+\w"
            if re.match(markdown_pattern, linha):
                linhas_finais.append(linha)
                continue
            
            if len(linha.strip()) >= min_tam:
                if re.search(r"[a-zA-ZÀ-ÿ0-9]", linha):
                    linhas_finais.append(linha)
        
        return "\n".join(linhas_finais).strip()
    
    def montar_documento_final(
        self, paginas_limpas: List[Tuple[int, str]], metadados_paginas: List[Dict]
    ) -> str:
        """Monta o documento final com cabeçalhos de página."""
        partes = []
        total_paginas = len(paginas_limpas)
        
        for idx, (numero_pagina, conteudo) in enumerate(paginas_limpas):
            metadados = None
            for meta in metadados_paginas:
                if meta.get("pagina_arquivo") == numero_pagina:
                    metadados = meta
                    break
            
            if total_paginas > 1:
                movimentacao = ""
                if metadados and "movimentacao_numero" in metadados:
                    mov_num = metadados["movimentacao_numero"]
                    mov_tipo = metadados.get("movimentacao_tipo", "")
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
        
        return "\n".join(partes).strip()
    
    def processar(
        self, arquivo_pdf: str, arquivo_txt: str, arquivo_md: str
    ) -> Tuple[str, str]:
        """Processa o PDF completo."""
        print("\n" + "=" * 70)
        print(f"PROCESSAMENTO DE PDF JURÍDICO v5.1 {'[OCR ATIVO]' if self.usar_ocr else ''}")
        print("=" * 70)
        
        if not self.padroes_limpeza:
            print("Padrões de limpeza não carregados!")
            return "", ""
        
        print("\n" + "=" * 70)
        print("ETAPA 1: Extração")
        print("=" * 70)
        texto_bruto, metadados_paginas = self.extrair_texto_pymupdf(arquivo_pdf)
        
        if not texto_bruto:
            return "", ""
        
        with open(arquivo_txt, "w", encoding="utf-8") as f:
            f.write(texto_bruto)
        print(f"\nSalvo: {arquivo_txt} ({len(texto_bruto):,} chars)")
        
        total_paginas = len(metadados_paginas)
        preservar_capa = total_paginas > 1
        
        if preservar_capa:
            print(f"\nDocumento com {total_paginas} páginas")
            print("A primeira página (capa) será preservada")
        
        print("\n" + "=" * 70)
        print("ETAPA 2: Separação por páginas")
        print("=" * 70)
        
        paginas_texto = self.separar_por_paginas(texto_bruto)
        print(f"   {len(paginas_texto)} página(s) separada(s)")
        
        print("\n" + "=" * 70)
        print("ETAPA 3: Limpeza por página")
        print("=" * 70)
        
        paginas_limpas = []
        for num_pag, conteudo_pag in paginas_texto:
            print(f"\n   Processando página {num_pag}...")
            
            if preservar_capa and num_pag == 1:
                print("      Página preservada (capa)")
                conteudo_limpo = conteudo_pag
            else:
                conteudo_limpo = self.remover_ruidos(conteudo_pag)
                conteudo_limpo = self.limpar_fragmentos_finais(conteudo_limpo)
            
            conteudo_final = self.normalizar_espacos(conteudo_limpo)
            
            linhas_uteis = [
                linha
                for linha in conteudo_final.split("\n")
                if linha.strip() and not re.match(r"^[\*\s]+$", linha.strip())
            ]
            
            if len(linhas_uteis) > 2:
                paginas_limpas.append((num_pag, conteudo_final))
                print(f"      {len(conteudo_final)} chars ({len(linhas_uteis)} linhas)")
            elif len(linhas_uteis) > 0:
                paginas_limpas.append((num_pag, conteudo_final))
                print(f"      Pouco conteúdo ({len(linhas_uteis)} linhas)")
            else:
                paginas_limpas.append((num_pag, "*Página sem conteúdo útil*"))
                print("      Página vazia")
        
        print("\n" + "=" * 70)
        print("ETAPA 4: Montagem")
        print("=" * 70)
        texto_final = self.montar_documento_final(paginas_limpas, metadados_paginas)
        print(f"   Documento com {len(paginas_limpas)} página(s)")
        
        print("\n" + "=" * 70)
        print("ESTATÍSTICAS")
        print("=" * 70)
        
        palavras = len(texto_final.split())
        reducao = len(texto_bruto) - len(texto_final)
        percentual = (reducao / len(texto_bruto) * 100) if texto_bruto else 0
        
        print(f"   Original: {len(texto_bruto):,} chars")
        print(f"   Removido: {reducao:,} chars ({percentual:.1f}%)")
        print(f"   Final: {len(texto_final):,} chars")
        print(f"   Palavras: {palavras}")
        
        with open(arquivo_md, "w", encoding="utf-8") as f:
            f.write(texto_final if texto_final else "*Documento vazio*\n")
        
        print(f"\nSalvo: {arquivo_md}")
        print("\n" + "=" * 70)
        print("CONCLUÍDO!")
        print("=" * 70 + "\n")
        
        return texto_bruto, texto_final


def main():
    """Função principal."""
    if len(sys.argv) < 2:
        print("Uso: python main.py <arquivo.pdf> [--sem-ocr]")
        return
    
    arquivo_pdf = sys.argv[1]
    usar_ocr = "--sem-ocr" not in sys.argv
    
    if not Path(arquivo_pdf).exists():
        print(f"Arquivo não encontrado: {arquivo_pdf}")
        return
    
    caminho = Path(arquivo_pdf)
    nome_base = caminho.stem
    diretorio = caminho.parent
    
    arquivo_txt = diretorio / f"{nome_base}_texto-extraido.txt"
    arquivo_md = diretorio / f"{nome_base}_texto-limpo.md"
    
    print(f"Entrada: {arquivo_pdf}")
    print(f"Saída 1: {arquivo_txt}")
    print(f"Saída 2: {arquivo_md}")
    
    processador = ProcessadorPDFJuridico(
        "limpeza.toml", 
        "hierarquia.toml",
        usar_ocr=usar_ocr
    )
    processador.processar(
        arquivo_pdf=arquivo_pdf,
        arquivo_txt=str(arquivo_txt),
        arquivo_md=str(arquivo_md),
    )


if __name__ == "__main__":
    main()