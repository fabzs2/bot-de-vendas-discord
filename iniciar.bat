@echo off
chcp 65001 > nul
title Bot de Vendas Discord • Inicializador Automático
color 0B

echo ============================================================
echo   🛒 INICIALIZADOR DO BOT DE VENDAS DISCORD (PIX AUTO)
echo ============================================================
echo.

:: 1. Verifica se o Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERRO] Python não foi detectado no sistema!
    echo Por favor, instale o Python 3.10 ou superior em: https://www.python.org/downloads/
    echo ATENÇÃO: Marque a caixa "Add Python to PATH" durante a instalação.
    echo.
    pause
    exit /b
)

:: 2. Cria ambiente virtual (VENV) se não existir
if not exist "venv" (
    echo [1/3] Criando ambiente virtual isolado (venv)...
    python -m venv venv
)

:: Ativa o ambiente virtual
call venv\Scripts\activate.bat

:: 3. Verifica o arquivo .env
if not exist ".env" (
    echo [2/3] Criando arquivo .env a partir do .env.example...
    copy .env.example .env > nul
    color 0E
    echo.
    echo ============================================================
    echo [ATENÇÃO] O arquivo .env foi criado!
    echo Abra o arquivo .env com o Bloco de Notas e insira seu DISCORD_TOKEN.
    echo ============================================================
    echo.
    pause
)

:: 4. Instala dependências
echo [3/3] Verificando dependências do projeto (requirements.txt)...
pip install -r requirements.txt --quiet --disable-pip-version-check

echo.
echo ============================================================
echo 🚀 INICIANDO BOT DE VENDAS DISCORD...
echo ============================================================
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    color 0C
    echo [ERRO] O bot encerrou com erro! Veja a mensagem acima.
    echo.
)

pause
