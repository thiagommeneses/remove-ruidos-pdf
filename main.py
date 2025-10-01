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
        dpi_ocr: int = 150,
        debug_imgs: bool = False,
    ):
        """Inicializa o processador com dois arquivos de configuração."""
        self.arquivo_limpeza = arquivo_limpeza
        self.arquivo_hierarquia = arquivo_hierarquia
        self.usar_ocr = usar_ocr and OCR_DISPONIVEL
        self.dpi_ocr = dpi_ocr
        self.debug_imgs = debug_imgs
        
        self.padroes_limpeza = self._carregar_padroes(arquivo_limpeza)
        self.padroes_hierarquia = self._carregar_padroes(arquivo_hierarquia)
        
        self.config_limpeza = self.padroes_limpeza.get("configuracoes", {})
        self.config_hierarquia = self.padroes_hierarquia.get("configuracoes", {})
        
        if self.usar_ocr:
            # Configuração MAIS RÁPIDA do Tesseract
            # PSM 6 = bloco uniforme de texto (ideal para documentos)
            # OEM 1 = motor neural network (mais rápido que OEM 3)
            self.tesseract_config = '--psm 6 --oem 1'
    
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
        Específico para PDFs jurídicos com documentos escaneados.
        
        Returns:
            'texto', 'imagem' ou 'hibrida'
        """
        texto = page.get_text()
        images = page.get_images(full=True)
        
        # Se não tem imagens, é puramente texto
        if len(images) == 0:
            return 'texto'
        
        # Heurística 1: Analisa tamanho das imagens em bytes
        # Imagens grandes (> 50KB) geralmente são documentos escaneados
        tem_imagem_grande = False
        for img_info in images:
            try:
                xref = img_info[0]
                base_image = page.parent.extract_image(xref)
                if base_image and len(base_image.get("image", b"")) > 50000:  # 50KB
                    tem_imagem_grande = True
                    break
            except:
                continue
        
        # Heurística 2: Proporção de texto vs imagens
        texto_limpo = texto.strip()
        num_chars = len(texto_limpo)
        num_images = len(images)
        
        # PDFs jurídicos típicos:
        # - Capa: texto puro, sem imagens ou imagens pequenas (logos)
        # - Documentos escaneados: muito texto extraível (metadados) + imagens grandes
        
        if tem_imagem_grande:
            # Se tem imagem grande, provavelmente é documento escaneado
            if num_chars > 200:
                # Muito texto + imagem grande = híbrida (texto é metadado, imagem é conteúdo)
                return 'hibrida'
            else:
                # Pouco texto + imagem grande = imagem pura
                return 'imagem'
        
        # Heurística 3: Múltiplas imagens pequenas podem ser logos/selos
        if num_images >= 2 and num_chars > 500:
            # Múltiplas imagens + muito texto = pode ser página híbrida
            return 'hibrida'
        
        # Pouco texto + alguma imagem = provavelmente escaneado
        if num_chars < 100 and num_images > 0:
            return 'imagem'
        
        # Padrão: página de texto
        return 'texto'
    
    def _preprocessar_imagem(self, img: Image.Image) -> Image.Image:
        """
        Pré-processa imagem para melhorar OCR em documentos jurídicos.
        Foco: remover ruído, melhorar contraste, binarizar.
        """
        # Converte para escala de cinza
        img = img.convert('L')
        
        # Converte para array numpy
        img_array = np.array(img)
        
        # 1. Aumenta contraste mais agressivamente
        img_array = np.clip(img_array * 1.5, 0, 255).astype(np.uint8)
        
        # 2. Aplicar threshold adaptativo (binarização)
        # Isso remove fundos cinzas e melhora muito o OCR
        from PIL import ImageFilter
        img = Image.fromarray(img_array)
        
        # Aumenta nitidez
        img = img.filter(ImageFilter.SHARPEN)
        
        # Binarização usando threshold de Otsu (simulado)
        img_array = np.array(img)
        threshold = np.mean(img_array) * 0.9  # Threshold adaptativo
        img_array = np.where(img_array > threshold, 255, 0).astype(np.uint8)
        
        # 3. Remove ruído de salt-and-pepper
        img = Image.fromarray(img_array)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        
        return img
    
    def _extrair_texto_ocr_pagina(self, page, page_num: int, debug_imgs: bool = False) -> str:
        """
        Extrai texto de uma página usando OCR otimizado.
        Tempo alvo: < 1s por página com 150 DPI.
        
        Args:
            page: Página do PyMuPDF
            page_num: Número da página
            debug_imgs: Se True, salva imagens pré-processadas para debug
        """
        try:
            # Renderiza página em imagem com DPI configurável
            pix = page.get_pixmap(dpi=self.dpi_ocr)
            
            # Converte para PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Salva imagem original se debug
            if debug_imgs:
                img.save(f"debug_pag{page_num}_original.png")
            
            # Pré-processa
            img_processada = self._preprocessar_imagem(img)
            
            # Salva imagem processada se debug
            if debug_imgs:
                img_processada.save(f"debug_pag{page_num}_processada.png")
                print(f"      💾 Imagens de debug salvas: debug_pag{page_num}_*.png")
            
            # OCR com Tesseract otimizado
            texto_ocr = pytesseract.image_to_string(
                img_processada,
                lang='por',
                config=self.tesseract_config
            )
            
            # Limpa caracteres problemáticos de encoding
            texto_limpo = self._limpar_encoding_ocr(texto_ocr)
            
            return texto_limpo.strip()
            
        except Exception as e:
            print(f"      ⚠️  Erro no OCR da página {page_num}: {e}")
            # Fallback: tenta extrair texto normal
            try:
                return page.get_text()
            except:
                return ""
    
    def _limpar_encoding_ocr(self, texto: str) -> str:
        """
        Limpa problemas comuns de encoding em OCR.
        Remove caracteres de controle e normaliza Unicode.
        """
        import unicodedata
        
        # Normaliza Unicode (NFKD = decomposição compatível)
        texto = unicodedata.normalize('NFKD', texto)
        
        # Remove caracteres de controle exceto \n, \t, \r
        texto_limpo = []
        for char in texto:
            cat = unicodedata.category(char)
            if cat[0] != 'C' or char in ['\n', '\t', '\r', ' ']:
                texto_limpo.append(char)
        
        texto = ''.join(texto_limpo)
        
        # Normaliza espaços
        texto = re.sub(r'[ \t]+', ' ', texto)
        
        return texto
    
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
            print("\n   Analisando tipo de cada página:")
            for i in range(total_paginas):
                tipo = self._detectar_tipo_pagina(doc[i])
                
                # Debug: mostra informações da detecção
                page = doc[i]
                texto = page.get_text()
                images = page.get_images(full=True)
                print(f"      Página {i+1}: {tipo.upper():8} | {len(texto):4} chars | {len(images)} imagens")
                
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
                    
                    md_pagina = self._extrair_texto_ocr_pagina(page, i + 1, debug_imgs=self.debug_imgs)
                    
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
        print("Uso: python main.py <arquivo.pdf> [opções]")
        print("\nOpções:")
        print("  --sem-ocr      Desativa OCR")
        print("  --dpi=N        Define DPI do OCR (padrão: 150)")
        print("  --debug        Salva imagens pré-processadas para debug")
        print("\nExemplos:")
        print("  python main.py doc.pdf")
        print("  python main.py doc.pdf --dpi=200")
        print("  python main.py doc.pdf --debug")
        return
    
    arquivo_pdf = sys.argv[1]
    usar_ocr = "--sem-ocr" not in sys.argv
    debug_imgs = "--debug" in sys.argv
    
    # Extrai DPI dos argumentos
    dpi_ocr = 150  # padrão
    for arg in sys.argv[2:]:
        if arg.startswith("--dpi="):
            try:
                dpi_ocr = int(arg.split("=")[1])
                print(f"DPI configurado: {dpi_ocr}")
            except ValueError:
                print("Valor de DPI inválido, usando padrão (150)")
    
    if debug_imgs:
        print("Modo DEBUG ativado - imagens serão salvas")
    
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
        usar_ocr=usar_ocr,
        dpi_ocr=dpi_ocr,
        debug_imgs=debug_imgs
    )
    processador.processar(
        arquivo_pdf=arquivo_pdf,
        arquivo_txt=str(arquivo_txt),
        arquivo_md=str(arquivo_md),
    )


if __name__ == "__main__":
    main()