#!/bin/bash
# Script para executar linters e formatadores no projeto
# Uso: ./lint.sh [comando]

# Ativa o ambiente virtual
source .venv/bin/activate

case "$1" in
    format)
        echo "🔧 Organizando imports..."
        isort main.py main_pymupdf.py
        echo "✨ Formatando código..."
        black main.py main_pymupdf.py
        echo "✅ Formatação concluída!"
        ;;
    
    check)
        echo "🔍 Verificando com Flake8..."
        flake8 main.py main_pymupdf.py
        echo ""
        echo "🔍 Verificando com Pylint..."
        pylint main.py main_pymupdf.py --max-line-length=88 --disable=C0111,C0103,R0913,R0914,R0912,R0915
        ;;
    
    flake8)
        echo "🔍 Executando Flake8..."
        flake8 main.py main_pymupdf.py
        ;;
    
    pylint)
        echo "🔍 Executando Pylint..."
        pylint main.py main_pymupdf.py --max-line-length=88
        ;;
    
    all)
        echo "🔧 Formatando código..."
        isort main.py main_pymupdf.py
        black main.py main_pymupdf.py
        echo ""
        echo "🔍 Verificando qualidade..."
        flake8 main.py main_pymupdf.py
        echo ""
        pylint main.py main_pymupdf.py --max-line-length=88 --disable=C0111,C0103,R0913,R0914,R0912,R0915
        echo ""
        echo "✅ Processo completo!"
        ;;
    
    *)
        echo "📋 Script de Linting e Formatação"
        echo ""
        echo "Uso: ./lint.sh [comando]"
        echo ""
        echo "Comandos disponíveis:"
        echo "  format   - Formata o código com isort e black"
        echo "  check    - Executa flake8 e pylint"
        echo "  flake8   - Executa apenas flake8"
        echo "  pylint   - Executa apenas pylint"
        echo "  all      - Formata e verifica (completo)"
        echo ""
        echo "Exemplo: ./lint.sh format"
        ;;
esac

