#!/usr/bin/env bash
# ============================================================
#   🛒 INICIALIZADOR DO BOT DE VENDAS DISCORD (Linux / macOS)
# ============================================================

set -e

# Cores para terminal
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  🛒 INICIALIZADOR DO BOT DE VENDAS DISCORD (PIX AUTO)${NC}"
echo -e "${BLUE}============================================================${NC}"

# 1. Verifica Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERRO] Python 3 não encontrado! Instale com: sudo apt install python3 python3-venv${NC}"
    exit 1
fi

# 2. Cria venv se não existir
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}[1/3] Criando ambiente virtual (venv)...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate

# 3. Verifica .env
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[2/3] Criando arquivo .env a partir do .env.example...${NC}"
    cp .env.example .env
    echo -e "${RED}[ATENÇÃO] Configure o DISCORD_TOKEN no arquivo .env antes de rodar!${NC}"
    exit 1
fi

# 4. Instala dependências
echo -e "${YELLOW}[3/3] Instalando dependências (requirements.txt)...${NC}"
pip install -r requirements.txt --quiet --disable-pip-version-check

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}🚀 INICIANDO BOT DE VENDAS DISCORD...${NC}"
echo -e "${GREEN}============================================================${NC}"

python3 main.py
