#!/usr/bin/env python3
import sys
import argparse
from datetime import datetime
from license_manager import license_mgr

BANNER = """
============================================================
🔑 GERADOR E GERENCIADOR DE LICENÇAS • BOT DE VENDAS DISCORD
============================================================
"""

def generate_key(client: str, guild_id: str, days: int):
    key = license_mgr.generate_license(client_name=client, guild_id=guild_id, days=days)
    
    print("\n" + "=" * 60)
    print("✅ LICENÇA GERADA COM SUCESSO!")
    print("=" * 60)
    print(f"👤 Cliente: {client}")
    print(f"🌐 Servidor Vinculado: {guild_id if guild_id != '*' else 'Todos os Servidores (*)'}")
    print(f"⏳ Validade: {'Vitalícia / Permanente' if days == 0 else f'{days} dias'}")
    print("\n📋 CHAVE DE LICENÇA (Copie e entregue ao comprador):")
    print(f"\n{key}\n")
    print("=" * 60)
    print("📌 Como o comprador deve usar:")
    print("1. Abrir o arquivo .env do bot")
    print(f"2. Colocar a linha: LICENSE_KEY={key}")
    print("3. Iniciar o bot normalmente!")
    print("=" * 60 + "\n")
    return key

def inspect_key(key: str):
    valid, msg, payload = license_mgr.verify_license_key(key)
    print("\n" + "=" * 60)
    print("🔍 INSPEÇÃO DE CHAVE DE LICENÇA")
    print("=" * 60)
    print(f"📊 Status: {'🟢 VÁLIDA' if valid else '🔴 INVÁLIDA'}")
    print(f"💬 Mensagem: {msg}")
    if payload:
        print(f"👤 Cliente: {payload.get('cli', 'N/A')}")
        print(f"🌐 Servidor (Guild ID): {payload.get('gid', '*')}")
        exp = payload.get('exp', 0)
        exp_txt = "Vitalícia" if exp == 0 else datetime.fromtimestamp(exp).strftime("%d/%m/%Y às %H:%M:%S")
        print(f"⏳ Expiração: {exp_txt}")
        iat = payload.get('iat', 0)
        iat_txt = datetime.fromtimestamp(iat).strftime("%d/%m/%Y às %H:%M:%S") if iat else "N/A"
        print(f"📅 Emitida em: {iat_txt}")
    print("=" * 60 + "\n")

def interactive_mode():
    print(BANNER)
    print("Escolha uma opção:")
    print("1. Gerar Nova Licença para um Cliente")
    print("2. Inspecionar / Validar uma Chave Existente")
    print("3. Sair")
    
    opcao = input("\n👉 Opção (1/2/3): ").strip()
    if opcao == "1":
        client = input("Nome ou Tag do Cliente (ex: João-GGMAX): ").strip() or "Cliente"
        guild_id = input("ID do Servidor Discord do cliente (Pressione Enter para liberar em qualquer servidor): ").strip() or "*"
        dias_str = input("Duração em dias (0 para Vitalícia): ").strip() or "0"
        days = int(dias_str) if dias_str.isdigit() else 0
        generate_key(client, guild_id, days)
    elif opcao == "2":
        key = input("Cole a Chave de Licença (LIC-...): ").strip()
        inspect_key(key)
    else:
        print("Até logo!")

def main():
    parser = argparse.ArgumentParser(description="Gerenciador de Licenças do Bot de Vendas Discord")
    subparsers = parser.add_subparsers(dest="command")

    # Comando generate
    gen_parser = subparsers.add_parser("generate", help="Gera uma nova chave de licença")
    gen_parser.add_argument("--client", "-c", type=str, default="Cliente", help="Nome ou identificador do comprador")
    gen_parser.add_argument("--guild", "-g", type=str, default="*", help="ID do servidor Discord (ou '*' para todos)")
    gen_parser.add_argument("--days", "-d", type=int, default=0, help="Quantidade de dias de validade (0 para vitalícia)")
    gen_parser.add_argument("--lifetime", action="store_true", help="Gera licença vitalícia (equivalente a --days 0)")

    # Comando inspect
    insp_parser = subparsers.add_parser("inspect", help="Inspeciona e valida uma chave de licença")
    insp_parser.add_argument("--key", "-k", type=str, required=True, help="Chave de licença (LIC-...)")

    args = parser.parse_args()

    if args.command == "generate":
        days = 0 if args.lifetime else args.days
        generate_key(args.client, args.guild, days)
    elif args.command == "inspect":
        inspect_key(args.key)
    else:
        interactive_mode()

if __name__ == "__main__":
    main()
