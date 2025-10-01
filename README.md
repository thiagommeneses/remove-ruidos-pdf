# EXTRACTJUR v5 - Extrator de PDF Jurídico v5.0
# Autor: MPGO - SubPLEI, Thiago Marques Meneses

Sistema avançado para extração, limpeza e estruturação de documentos jurídicos em PDF.

## Características

- ✅ **Extração com PyMuPDF4LLM** - Preserva formatação markdown
- ✅ **Hierarquia automática** - Detecta H1, H2, H3, H4 em documentos
- ✅ **Preservação inteligente** - Protege conteúdo jurídico importante
- ✅ **Limpeza avançada** - Remove metadados, carimbos e ruídos
- ✅ **Suporte a múltiplas páginas** - Identifica movimentações
- ✅ **Capa preservada** - Primeira página intacta em documentos multipáginas

## Instalação

```bash
# Instale as dependências
pip install pymupdf pymupdf4llm toml

# Clone ou baixe os arquivos
# - processar_pdf.py
# - limpeza.toml
# - hierarquia.toml
```

## Estrutura de Arquivos

```
projeto/
├── processar_pdf.py      # Script principal
├── limpeza.toml          # Padrões de remoção de ruídos
├── hierarquia.toml       # Configuração de estruturação
└── seus_pdfs/
    ├── documento1.pdf
    ├── documento2.pdf
    └── ...
```

## Uso

### Comando Básico

```bash
python processar_pdf.py documento.pdf
```

### Saídas Geradas

```
documento.pdf
├── documento_texto-extraido.txt    # Texto bruto extraído
└── documento_texto-limpo.md        # Markdown limpo e estruturado
```

## Arquivos de Configuração

### limpeza.toml

Controla a **remoção de ruídos**:

```toml
[metadados_processuais]
patterns = [
    "Processo:\\s*[\\d\\.-]+",
    "Movimentacao\\s+\\d+\\s*:\\s*\\w+",
    # ... mais padrões
]

[configuracoes]
ordem_processamento = [
    "metadados_processuais",
    "assinaturas_digitais",
    "cabecalhos_institucionais",
    # ... ordem de aplicação
]
```

### hierarquia.toml

Controla a **estruturação do documento**:

```toml
[header_config.h1]
patterns = [
    "AUTO DE PRISÃO EM FLAGRANTE",
    "TERMO DE DEPOIMENTO",
    # ... documentos principais
]

[padroes_preservar]
patterns = [
    "NARRATIVA",
    "RELATO PM:",
    # ... conteúdo a preservar
]
```

## Exemplos de Uso

### Documento com 1 página

```bash
python processar_pdf.py IP1-pagina-7.pdf
```

**Resultado:**
```markdown
# AUTO DE PRISÃO EM FLAGRANTE

## DADOS DO REGISTRO

Nome: João da Silva
CPF: 123.456.789-00

## NARRATIVA

No dia 15/05/2024, às 10h30...
```

### Documento com múltiplas páginas

```bash
python processar_pdf.py Processo-Completo.pdf
```

**Resultado:**
```markdown
============================================================
PÁGINA 1
============================================================

Processo Nº: 5607437-31.2024.8.09.0085

1. Dados Processo
Juízo: Itapuranga - Vara Criminal
[... capa preservada intacta ...]

============================================================
PÁGINA 2 | MOVIMENTAÇÃO 1 (Recebido)
============================================================

# PORTARIA

## NARRATIVA

A Polícia Civil do Estado de Goiás...

============================================================
PÁGINA 3 | MOVIMENTAÇÃO 2 (Distribuído)
============================================================

# REGISTRO DE ATENDIMENTO INTEGRADO

## DADOS DO FATO

Data: 20/12/2023
Local: Rua XV de Novembro, 123
```

## Personalização

### Adicionar novo padrão de limpeza

Edite `limpeza.toml`:

```toml
[sua_nova_secao]
description = "Remove XYZ"
patterns = [
    '''seu_padrao_regex_aqui''',
]
```

Adicione na ordem de processamento:

```toml
[configuracoes]
ordem_processamento = [
    "metadados_processuais",
    "sua_nova_secao",  # ← adicione aqui
    "assinaturas_digitais",
    # ...
]
```

### Adicionar novo tipo de cabeçalho

Edite `hierarquia.toml`:

```toml
[header_config.h1]
patterns = [
    "AUTO DE PRISÃO EM FLAGRANTE",
    "SEU NOVO DOCUMENTO AQUI",  # ← adicione aqui
]
```

### Preservar novo tipo de conteúdo

Edite `hierarquia.toml`:

```toml
[padroes_preservar]
patterns = [
    "NARRATIVA",
    '''Seu novo padrão:.*''',  # ← adicione aqui
]
```

## Funcionalidades Avançadas

### Preservação de Conteúdo

O sistema protege automaticamente:
- Narrativas policiais
- Relatos (PM/PC)
- Dados processuais importantes
- Informações de partes (réu, vítima, testemunhas)
- Cálculos de pena
- Laudos periciais

### Hierarquia Automática

Detecta e formata:
- **H1** - Documentos principais (Auto de Prisão, Mandado, etc.)
- **H2** - Seções estruturais (Dados Processo, Narrativa, etc.)
- **H3** - Subseções (Polo Ativo, Polo Passivo, etc.)
- **H4** - Títulos específicos

### Remoção Inteligente

Remove automaticamente:
- Cabeçalhos institucionais repetidos
- Metadados de sistema
- Assinaturas digitais e tokens
- Códigos de validação
- URLs e links administrativos
- Paginação e numeração
- Endereços e telefones institucionais
- Carimbos de data/hora de sistema

## Saída do Console

```
📁 Entrada: documento.pdf
📄 Saída 1: documento_texto-extraido.txt
📄 Saída 2: documento_texto-limpo.md
✅ limpeza.toml carregado: v4.1.0
✅ hierarquia.toml carregado: v1.0.0

======================================================================
🔍 PROCESSAMENTO DE PDF JURÍDICO v5.0 - PyMuPDF4LLM
======================================================================

======================================================================
📖 ETAPA 1: Extração com PyMuPDF4LLM
======================================================================
📄 Extraindo com PyMuPDF4LLM...
   ✓ 3 página(s) encontradas
   ✓ Página 1/3 (2345 chars)
   ✓ Página 2/3 (1876 chars)
      → Movimentação 1: Recebido
   ✓ Página 3/3 (2103 chars)
      → Movimentação 1: Recebido

💾 Salvo: documento_texto-extraido.txt (6,324 chars)

======================================================================
📐 ETAPA 2: Aplicação de Hierarquia
======================================================================
📐 Aplicando hierarquia de cabeçalhos...
   ✓ Hierarquia aplicada

   📋 Documento com 3 páginas
   ℹ️  A primeira página (capa) será preservada intacta

======================================================================
📑 ETAPA 3: Separação por páginas
======================================================================
   🔍 Marcadores encontrados: 3
      • Página 1: 2345 chars
      • Página 2: 1876 chars
      • Página 3: 2103 chars
   ✓ 3 página(s) separada(s)

======================================================================
🧹 ETAPA 4: Limpeza por página
======================================================================

   Processando página 1...
      Página preservada (capa do processo)
      2345 chars finais

   Processando página 2...
🔒 Protegendo conteúdo importante...
   ✓ 12 blocos protegidos
      1456 chars finais

   Processando página 3...
🔒 Protegendo conteúdo importante...
   ✓ 8 blocos protegidos
      1789 chars finais

======================================================================
📄 ETAPA 5: Montagem do documento
======================================================================
   Documento montado com 3 página(s)

======================================================================
📊 ESTATÍSTICAS
======================================================================
   Original: 6,324 chars
   Removido: 1,734 chars (27.4%)
   Final: 4,590 chars
   Linhas: 145
   Palavras: 678

💾 Salvo: documento_texto-limpo.md

======================================================================
✅ PROCESSAMENTO CONCLUÍDO!
======================================================================

✅ 678 palavras no documento final
```

## Solução de Problemas

### PyMuPDF4LLM não instalado

```bash
pip install pymupdf4llm
```

### Erro ao carregar TOML

Verifique a sintaxe do arquivo TOML. Use aspas simples triplas para regex:

```toml
patterns = [
    '''seu_padrao_aqui''',
]
```

### Conteúdo importante sendo removido

Adicione o padrão em `hierarquia.toml` na seção `[padroes_preservar]`.

### Muito ruído permanecendo

Adicione novos padrões em `limpeza.toml` e inclua a seção na ordem de processamento.

## Versão

- **v5.0** - Sistema completo com PyMuPDF4LLM e hierarquia
- **v4.2** - Sistema básico com PyPDF2
- **v3.0** - Primeira versão com separação de páginas

## Licença

Uso livre para fins educacionais e profissionais.