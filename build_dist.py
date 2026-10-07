#!/usr/bin/env python3
import os
import sys
import shutil
import zipfile
import py_compile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(DIST_DIR, "bot_vendas")

# Arquivos e diretórios essenciais para o funcionamento do bot
INCLUDE_FILES = [
    "main.py",
    "database.py",
    "payments.py",
    "license_manager.py",
    "requirements.txt",
    ".env.example",
    "README.md",
    "iniciar.bat",
    "iniciar.sh",
    "Dockerfile",
    "docker-compose.yml",
    "discloud.config",
    "squarecloud.app"
]

INCLUDE_DIRS = [
    "cogs"
]

IGNORE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.db",
    "*.sqlite",
    ".env",
    ".git*",
    "dist",
    "scratch"
]

def clean_build():
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)

def copy_files():
    print("📦 [1/3] Copiando arquivos essenciais para o pacote...")
    for filename in INCLUDE_FILES:
        src = os.path.join(BASE_DIR, filename)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(BUILD_DIR, filename))
        else:
            print(f"⚠️ Aviso: Arquivo opcional '{filename}' não encontrado.")

    for dirname in INCLUDE_DIRS:
        src = os.path.join(BASE_DIR, dirname)
        dst = os.path.join(BUILD_DIR, dirname)
        if os.path.exists(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))

def compile_code(compile_mode: bool = False):
    if not compile_mode:
        return
    print("🔒 [2/3] Compilando arquivos Python para Bytecode (.pyc)...")
    for root, _, files in os.walk(BUILD_DIR):
        for f in files:
            if f.endswith(".py") and f != "main.py": # Mantém main.py como ponto de entrada ou compila tudo
                py_path = os.path.join(root, f)
                pyc_path = py_path + "c"
                py_compile.compile(py_path, pyc_path, doraise=True)
                os.remove(py_path)

def create_zip():
    print("🗜️ [3/3] Criando arquivo ZIP pronto para envio ao cliente...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = os.path.join(DIST_DIR, f"bot_vendas_pronto_{timestamp}.zip")
    
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(BUILD_DIR):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, BUILD_DIR)
                zipf.write(full_path, rel_path)

    print("\n" + "=" * 60)
    print("🎉 PACOTE DE DISTRIBUIÇÃO GERADO COM SUCESSO!")
    print("=" * 60)
    print(f"📁 Pasta dos arquivos: {BUILD_DIR}")
    print(f"📦 Arquivo ZIP Final: {zip_filename}")
    print(f"⚖️ Tamanho do ZIP: {os.path.getsize(zip_filename) / 1024:.2f} KB")
    print("=" * 60)
    print("✨ Esse arquivo .zip está 100% limpo, sem seu token real e sem seu banco de dados!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    compile_flag = "--compile" in sys.argv
    clean_build()
    copy_files()
    compile_code(compile_flag)
    create_zip()
