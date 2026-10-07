import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

TOKEN = os.getenv('DISCORD_TOKEN')
CARGO_VIP_STR = os.getenv('CARGO_VIP', '0')
ID_CARGO_VIP = int(CARGO_VIP_STR) if CARGO_VIP_STR.isdigit() else None

import database as db
from payments import gateway
from license_manager import license_mgr
from cogs.sales import PainelLojaView, ReviewButtonView

class SalesBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        print("🔄 [1/4] Inicializando banco de dados SQLite Multi-Tenant...")
        await db.init_db(default_cargo_id=ID_CARGO_VIP)

        print("🔄 [2/4] Carregando extensões e módulos...")
        await self.load_extension('cogs.sales')
        await self.load_extension('cogs.admin')

        print("🔄 [3/4] Registrando views persistentes...")
        self.add_view(PainelLojaView())
        self.add_view(ReviewButtonView(pedido_codigo="persistent", produto_nome="Produto"))

        print("🔄 [4/4] Sincronizando comandos Slash (/)...")
        try:
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} comandos Slash sincronizados com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao sincronizar comandos Slash: {e}")

    async def on_ready(self):
        # Validação de Licença
        lic_key = os.getenv("LICENSE_KEY", "").strip()
        if lic_key:
            lic_ok, lic_msg, lic_data = license_mgr.verify_license_key(lic_key)
            status_lic = f"🟢 Ativa ({lic_data.get('cli', 'Cliente')})" if lic_ok else f"🔴 {lic_msg}"
        else:
            status_lic = "🟡 Modo Livre / Self-Hosted (Sem restrição)"

        modo_gateway = "Simulação / Teste (Dev)" if gateway.is_simulation() else "Mercado Pago PIX Oficial"
        produtos = await db.get_produtos(apenas_ativos=True)

        print("=" * 60)
        print(f"💎 BOT DE VENDAS DISCORD INICIALIZADO COM SUCESSO!")
        print(f"🤖 Bot: {self.user} (ID: {self.user.id})")
        print(f"🌐 Servidores Conectados: {len(self.guilds)}")
        print(f"🔑 Status da Licença: {status_lic}")
        print(f"💳 Gateway Padrão: {modo_gateway}")
        print(f"🏢 Arquitetura: Multi-Tenant (Isolamento por Servidor)")
        print(f"📦 Produtos Ativos Globais: {len(produtos)}")
        print(f"👑 Cargo VIP Padrão: {ID_CARGO_VIP}")
        print("=" * 60)

        # Status personalizado
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="🛍️ Loja Automática • Pix Instantâneo"
            ),
            status=discord.Status.online
        )

        # Sincronização instantânea dos comandos Slash para cada servidor conectado
        print("⚡ [Slash] Sincronizando comandos Slash instantaneamente nos servidores...")
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                synced_guild = await self.tree.sync(guild=guild)
                print(f"   ↳ 🟢 Servidor '{guild.name}' ({guild.id}): {len(synced_guild)} comandos sincronizados!")
            except Exception as err:
                print(f"   ↳ ⚠️ Erro ao sincronizar no servidor '{guild.name}': {err}")

    async def on_guild_join(self, guild: discord.Guild):
        auth, msg = license_mgr.is_guild_authorized(guild.id)
        if not auth:
            print(f"⚠️ Servidor não autorizado detectado: {guild.name} ({guild.id}). Motivo: {msg}")
            try:
                if guild.system_channel:
                    await guild.system_channel.send(
                        f"⚠️ **Atenção:** Este bot possui proteção de licença e o servidor `{guild.id}` não está autorizado.\n"
                        f"Entre em contato com o desenvolvedor para ativar sua chave de licença."
                    )
            except Exception:
                pass

        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"⚡ [Slash] Comandos sincronizados no novo servidor: {guild.name}")
        except Exception as err:
            print(f"⚠️ Erro ao sincronizar comandos na nova guild {guild.id}: {err}")

bot = SalesBot()

# ==============================================================================
# COMANDOS PREFIXO (!sync e !enviarpainel)
# ==============================================================================
@bot.command(name='sync')
@commands.has_permissions(administrator=True)
async def sync_comandos(ctx):
    """Sincroniza instantaneamente todos os comandos slash neste servidor"""
    msg = await ctx.send("🔄 Sincronizando comandos Slash neste servidor...")
    try:
        bot.tree.copy_global_to(guild=ctx.guild)
        synced = await bot.tree.sync(guild=ctx.guild)
        cmds_str = ", ".join([f"`/{c.name}`" for c in synced])
        await msg.edit(content=f"✅ **{len(synced)} comandos Slash sincronizados com sucesso neste servidor!**\n📋 Comandos disponíveis: {cmds_str}\n\n💡 *Dica:* Se os comandos não aparecerem imediatamente no seu Discord, pressione `Ctrl + R` (ou feche e abra o Discord) para atualizar o cache do app.")
    except Exception as e:
        await msg.edit(content=f"❌ Erro ao sincronizar comandos: {e}")

@bot.command(name='enviarpainel')
@commands.has_permissions(administrator=True)
async def enviar_painel_legado(ctx):
    """Permite enviar o novo painel moderno também pelo comando com prefixo !"""
    produtos = await db.get_produtos(guild_id=ctx.guild.id, apenas_ativos=True)
    if not produtos:
        return await ctx.send("⚠️ Nenhum produto cadastrado neste servidor. Use `/produto criar` para adicionar produtos.")

    embed = discord.Embed(
        title="🛒 Loja Automática • Catálogo de Produtos",
        description="Seja muito bem-vindo(a) à nossa loja oficial!\n"
                    "Escolha um dos produtos abaixo para abrir seu carrinho seguro e realizar a compra com **entrega 100% automática via Pix**.\n\n"
                    "💎 *Qualidade garantida, atendimento ágil e segurança total.*",
        color=0x5865F2
    )

    for p in produtos:
        emoji = p.get("emoji") or "📦"
        if p["tipo"] in ("digital", "ambos"):
            qtd = await db.get_estoque_count(p["id"])
            estoque_info = f"📦 `{qtd} em estoque`" if qtd > 0 else "🔴 *Esgotado*"
        else:
            estoque_info = "👑 *Cargo Automático*"

        embed.add_field(
            name=f"{emoji} {p['nome']} • R$ {p['preco']:.2f}",
            value=f"{p.get('descricao', 'Sem descrição.')}\n{estoque_info}",
            inline=False
        )

    embed.set_footer(text="Clique no menu ou botão abaixo para comprar instantaneamente!")
    view = PainelLojaView(produtos)
    await ctx.send(embed=embed, view=view)


# ==============================================================================
# TRATAMENTO DE ERROS DE COMANDOS SLASH
# ==============================================================================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.MissingPermissions):
        msg = "❌ Você não tem permissão de Administrador para usar este comando."
    else:
        msg = f"❌ Ocorreu um erro ao processar o comando: {error}"

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == '__main__':
    if not TOKEN:
        print("❌ ERRO FATAL: DISCORD_TOKEN não encontrado no arquivo .env!")
        print("Por favor, preencha o arquivo .env conforme o .env.example.")
        sys.exit(1)
    
    bot.run(TOKEN)
