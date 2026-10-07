import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

import database as db
from payments import gateway
from cogs.sales import (
    PainelLojaView,
    ItemLojaView,
    gerar_embed_produto_individual,
    gerar_embed_vitrine_produtos
)

# ==============================================================================
# MODAIS INTERATIVOS DE ADMINISTRAÇÃO
# ==============================================================================

class CriarProdutoModal(discord.ui.Modal, title="➕ Cadastrar Novo Produto"):
    nome = discord.ui.TextInput(
        label="Nome do Produto",
        placeholder="Ex: Nitro Mensal, Chave Steam, Cargo VIP...",
        max_length=100,
        required=True
    )
    preco = discord.ui.TextInput(
        label="Preço em Reais (R$)",
        placeholder="Ex: 15.00 ou 29.90",
        max_length=10,
        required=True
    )
    tipo = discord.ui.TextInput(
        label="Tipo (digital / cargo / ambos)",
        placeholder="digital (chaves/contas), cargo (VIP) ou ambos",
        default="digital",
        max_length=10,
        required=True
    )
    emoji = discord.ui.TextInput(
        label="Emoji do Produto",
        placeholder="Ex: 📦, ⭐, 🔑, 🎮",
        default="📦",
        max_length=10,
        required=False
    )
    descricao = discord.ui.TextInput(
        label="Descrição / Benefícios",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva o que o comprador receberá e instruções...",
        max_length=400,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            valor_preco = float(self.preco.value.replace(",", ".").strip())
            if valor_preco <= 0:
                raise ValueError()
        except ValueError:
            return await interaction.response.send_message("❌ Preço inválido! Digite um valor numérico positivo (ex: 15.00).", ephemeral=True)

        tipo_val = self.tipo.value.strip().lower()
        if tipo_val not in ("digital", "cargo", "ambos"):
            return await interaction.response.send_message("❌ Tipo inválido! Use apenas `digital`, `cargo` ou `ambos`.", ephemeral=True)

        emoji_val = self.emoji.value.strip() or "📦"
        desc_val = self.descricao.value.strip() or "Sem descrição."

        prod_id = await db.add_produto(
            nome=self.nome.value.strip(),
            descricao=desc_val,
            preco=round(valor_preco, 2),
            tipo=tipo_val,
            cargo_id=None,
            emoji=emoji_val,
            guild_id=interaction.guild_id
        )

        embed = discord.Embed(
            title="✅ Produto Cadastrado com Sucesso!",
            description=f"O produto **{emoji_val} {self.nome.value.strip()}** foi registrado na loja!\n\n"
                        f"🆔 **ID:** `#{prod_id}`\n"
                        f"💵 **Preço:** `R$ {valor_preco:.2f}`\n"
                        f"📦 **Tipo:** `{tipo_val.capitalize()}`\n\n"
                        f"💡 *Se este produto for do tipo digital, você já pode abastecer o estoque dele pelo menu!*",
            color=0x00D166
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AddEstoqueModal(discord.ui.Modal, title="📦 Adicionar Itens ao Estoque"):
    itens_input = discord.ui.TextInput(
        label="Itens/Chaves (1 por linha)",
        style=discord.TextStyle.paragraph,
        placeholder="KEY-1234-ABCD\nKEY-5678-EFGH\nusuario:senha",
        required=True,
        max_length=4000
    )

    def __init__(self, produto_id: int, produto_nome: str):
        super().__init__()
        self.produto_id = produto_id
        self.produto_nome = produto_nome

    async def on_submit(self, interaction: discord.Interaction):
        linhas = [l.strip() for l in self.itens_input.value.split("\n") if l.strip()]
        if not linhas:
            return await interaction.response.send_message("❌ Nenhum item válido encontrado.", ephemeral=True)

        qtd_adicionada = await db.add_estoque_itens(self.produto_id, linhas)
        total_atual = await db.get_estoque_count(self.produto_id)

        embed = discord.Embed(
            title="✅ Estoque Atualizado com Sucesso!",
            description=f"Foram adicionados **{qtd_adicionada}** novo(s) item(ns) para **{self.produto_nome}**.\n"
                        f"📊 **Estoque Total Disponível:** `{total_atual} unidade(s)`",
            color=0x00D166
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CriarCupomModal(discord.ui.Modal, title="🎟️ Criar Cupom de Desconto"):
    codigo = discord.ui.TextInput(
        label="Código do Cupom",
        placeholder="Ex: PROMO10, BLACKFRIDAY, BEMVINDO",
        max_length=20,
        required=True
    )
    tipo = discord.ui.TextInput(
        label="Tipo (percent para % ou fixo para R$)",
        placeholder="percent ou fixo",
        default="percent",
        max_length=10,
        required=True
    )
    valor = discord.ui.TextInput(
        label="Valor do Desconto",
        placeholder="Ex: 10 (para 10%) ou 5.00 (para R$ 5,00)",
        max_length=10,
        required=True
    )
    usos = discord.ui.TextInput(
        label="Limite de Resgates",
        placeholder="Ex: 50",
        default="100",
        max_length=10,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = float(self.valor.value.replace(",", ".").strip())
            if val <= 0:
                raise ValueError()
        except ValueError:
            return await interaction.response.send_message("❌ Valor de desconto inválido.", ephemeral=True)

        tipo_val = self.tipo.value.strip().lower()
        if tipo_val not in ("percent", "fixo"):
            return await interaction.response.send_message("❌ Tipo inválido! Use `percent` ou `fixo`.", ephemeral=True)

        usos_val = int(self.usos.value.strip()) if self.usos.value.strip().isdigit() else 100
        cod_val = self.codigo.value.strip().upper()

        await db.add_cupom(cod_val, tipo_val, round(val, 2), usos_val, guild_id=interaction.guild_id)
        desc_txt = f"{val}% OFF" if tipo_val == "percent" else f"R$ {val:.2f} OFF"

        embed = discord.Embed(
            title="🎟️ Cupom Criado com Sucesso!",
            description=f"**Código:** `{cod_val}`\n"
                        f"**Benefício:** `{desc_txt}`\n"
                        f"**Limite:** `{usos_val} usos`",
            color=0x00D166
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfigurarPixModal(discord.ui.Modal, title="💳 Configurar Mercado Pago (Pix)"):
    token_input = discord.ui.TextInput(
        label="Access Token de Produção",
        placeholder="Cole seu token APP_USR-xxxxxxxxxxxxxxxxxxxxxxxxxx aqui",
        style=discord.TextStyle.paragraph,
        max_length=200,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        token_clean = self.token_input.value.strip()
        if not token_clean.startswith("APP_USR-") and not token_clean.startswith("TEST-"):
            return await interaction.response.send_message("❌ Token inválido! Deve iniciar com `APP_USR-` ou `TEST-`.", ephemeral=True)

        await db.set_guild_mercadopago_token(interaction.guild_id, token_clean)
        token_mascarado = token_clean[:10] + "..." + token_clean[-4:]

        embed = discord.Embed(
            title="💳 Mercado Pago Configurado com Sucesso!",
            description=f"O token Pix deste servidor foi salvo de forma isolada.\n"
                        f"🔒 **Token Ativo:** `{token_mascarado}`\n\n"
                        f"Todas as vendas em **{interaction.guild.name}** cairão diretamente na conta associada a este token!",
            color=0x00D166
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==============================================================================
# SUB-VIEWS INTERATIVAS DO PAINEL
# ==============================================================================

class SeletorEstoqueSelect(discord.ui.Select):
    """Dropdown para selecionar qual produto abastecer."""
    def __init__(self, produtos: list[dict]):
        options = []
        for p in produtos[:25]:
            if p["tipo"] in ("digital", "ambos"):
                options.append(discord.SelectOption(
                    label=p["nome"][:100],
                    value=str(p["id"]),
                    description=f"ID #{p['id']} • R$ {p['preco']:.2f}",
                    emoji=p.get("emoji") or "📦"
                ))

        if not options:
            options.append(discord.SelectOption(label="Nenhum produto digital cadastrado", value="none"))

        super().__init__(placeholder="📦 Escolha o produto para abastecer estoque...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("⚠️ Não há produtos do tipo digital ou ambos cadastrados.", ephemeral=True)

        prod_id = int(self.values[0])
        prod = await db.get_produto_by_id(prod_id)
        if not prod:
            return await interaction.response.send_message("❌ Produto não encontrado.", ephemeral=True)

        await interaction.response.send_modal(AddEstoqueModal(prod["id"], prod["nome"]))


class SeletorEstoqueView(discord.ui.View):
    def __init__(self, produtos: list[dict]):
        super().__init__(timeout=300)
        self.add_item(SeletorEstoqueSelect(produtos))

    @discord.ui.button(label="Voltar ao Painel", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def btn_voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await gerar_embed_painel_admin(interaction.guild)
        view = PainelAdminView()
        await interaction.response.edit_message(embed=embed, view=view)


class GerenciarProdutosSelect(discord.ui.Select):
    """Dropdown para selecionar um produto para editar/deletar."""
    def __init__(self, produtos: list[dict]):
        options = []
        for p in produtos[:25]:
            options.append(discord.SelectOption(
                label=p["nome"][:100],
                value=str(p["id"]),
                description=f"ID #{p['id']} • R$ {p['preco']:.2f} ({p['tipo']})",
                emoji=p.get("emoji") or "📦"
            ))
        super().__init__(placeholder="🔍 Selecione um produto para gerenciar...", options=options)

    async def callback(self, interaction: discord.Interaction):
        prod_id = int(self.values[0])
        prod = await db.get_produto_by_id(prod_id)
        if not prod:
            return await interaction.response.send_message("❌ Produto não encontrado.", ephemeral=True)

        qtd = await db.get_estoque_count(prod_id) if prod["tipo"] in ("digital", "ambos") else "N/A"
        embed = discord.Embed(
            title=f"📦 Gerenciar: {prod.get('emoji', '📦')} {prod['nome']}",
            description=f"**ID:** `#{prod['id']}`\n"
                        f"**Preço:** `R$ {prod['preco']:.2f}`\n"
                        f"**Tipo:** `{prod['tipo'].capitalize()}`\n"
                        f"**Estoque Disponível:** `{qtd}`\n"
                        f"**Descrição:** {prod.get('descricao', 'Nenhuma')}",
            color=0x5865F2
        )
        view = ProdutoDetalheView(prod)
        await interaction.response.edit_message(embed=embed, view=view)


class GerenciarProdutosView(discord.ui.View):
    def __init__(self, produtos: list[dict]):
        super().__init__(timeout=300)
        self.add_item(GerenciarProdutosSelect(produtos))

    @discord.ui.button(label="Voltar ao Painel", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def btn_voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await gerar_embed_painel_admin(interaction.guild)
        view = PainelAdminView()
        await interaction.response.edit_message(embed=embed, view=view)


class ProdutoDetalheView(discord.ui.View):
    """Ações específicas em um produto (adicionar estoque, limpar, deletar)."""
    def __init__(self, produto: dict):
        super().__init__(timeout=300)
        self.produto = produto

    @discord.ui.button(label="Abastecer Estoque", style=discord.ButtonStyle.primary, emoji="➕", row=0)
    async def btn_add_estoque(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.produto["tipo"] == "cargo":
            return await interaction.response.send_message("⚠️ Este produto é do tipo Cargo VIP e não utiliza chaves digitais.", ephemeral=True)
        await interaction.response.send_modal(AddEstoqueModal(self.produto["id"], self.produto["nome"]))

    @discord.ui.button(label="Zerar Estoque", style=discord.ButtonStyle.secondary, emoji="🧹", row=0)
    async def btn_limpar_estoque(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.limpar_estoque(self.produto["id"])
        await interaction.response.send_message(f"🧹 O estoque de **{self.produto['nome']}** foi zerado com sucesso.", ephemeral=True)

    @discord.ui.button(label="Deletar Produto", style=discord.ButtonStyle.danger, emoji="🗑️", row=0)
    async def btn_deletar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.delete_produto(self.produto["id"], guild_id=interaction.guild_id)
        embed = discord.Embed(
            title="🗑️ Produto Deletado",
            description=f"O produto **{self.produto['nome']}** e seu estoque foram removidos da loja.",
            color=0xED4245
        )
        view = PainelAdminView()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Voltar aos Produtos", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def btn_voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        produtos = await db.get_produtos(guild_id=interaction.guild_id, apenas_ativos=False)
        embed = discord.Embed(
            title="📋 Gerenciamento de Produtos",
            description="Selecione um produto no menu abaixo para inspecionar, adicionar estoque ou excluir:",
            color=0x5865F2
        )
        view = GerenciarProdutosView(produtos)
        await interaction.response.edit_message(embed=embed, view=view)


class CuponsSelect(discord.ui.Select):
    """Dropdown para remover cupom."""
    def __init__(self, cupons: list[dict]):
        options = []
        for c in cupons[:25]:
            desc = f"{c['valor']}% OFF" if c["tipo"] == "percent" else f"R$ {c['valor']:.2f} OFF"
            options.append(discord.SelectOption(
                label=f"Excluir: {c['codigo']}",
                value=c["codigo"],
                description=f"{desc} • {c['usos_restantes']} usos restantes",
                emoji="🗑️"
            ))
        super().__init__(placeholder="Selecione um cupom para deletar...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cod = self.values[0]
        await db.delete_cupom(cod, guild_id=interaction.guild_id)
        await interaction.response.send_message(f"🗑️ O cupom `{cod}` foi excluído com sucesso!", ephemeral=True)


class GerenciarCuponsView(discord.ui.View):
    def __init__(self, cupons: list[dict]):
        super().__init__(timeout=300)
        if cupons:
            self.add_item(CuponsSelect(cupons))

    @discord.ui.button(label="Criar Novo Cupom", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def btn_criar_cupom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CriarCupomModal())

    @discord.ui.button(label="Voltar ao Painel", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def btn_voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await gerar_embed_painel_admin(interaction.guild)
        view = PainelAdminView()
        await interaction.response.edit_message(embed=embed, view=view)


# ==============================================================================
# MENU PRINCIPAL DO PAINEL DE ADMINISTRAÇÃO
# ==============================================================================

class AdminActionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Criar Novo Produto",
                value="criar_produto",
                description="Cadastra um novo produto (Digital, Cargo ou Ambos)",
                emoji="➕"
            ),
            discord.SelectOption(
                label="Abastecer Estoque Digital",
                value="add_estoque",
                description="Cola chaves, contas ou licenças no estoque",
                emoji="📦"
            ),
            discord.SelectOption(
                label="Gerenciar / Deletar Produtos",
                value="gerenciar_produtos",
                description="Visualiza estoque, zera estoque ou remove produtos",
                emoji="📋"
            ),
            discord.SelectOption(
                label="Cupons de Desconto",
                value="gerenciar_cupons",
                description="Cria, lista ou deleta cupons de desconto",
                emoji="🎟️"
            ),
            discord.SelectOption(
                label="Configurar Pix (Mercado Pago)",
                value="config_pix",
                description="Altera o Access Token Pix deste servidor",
                emoji="💳"
            ),
            discord.SelectOption(
                label="Publicar Vitrine na Loja",
                value="publicar_vitrine",
                description="Envia o painel de compras público no canal",
                emoji="📢"
            ),
            discord.SelectOption(
                label="Relatório Financeiro",
                value="relatorio_financeiro",
                description="Ver faturamento diário, histórico e mais vendidos",
                emoji="📈"
            ),
        ]
        super().__init__(
            placeholder="⚡ Escolha o que deseja fazer na loja...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_admin_main"
        )

    async def callback(self, interaction: discord.Interaction):
        escolha = self.values[0]
        guild_id = interaction.guild_id

        # 1. CRIAR NOVO PRODUTO
        if escolha == "criar_produto":
            return await interaction.response.send_modal(CriarProdutoModal())

        # 2. ABASTECER ESTOQUE
        elif escolha == "add_estoque":
            produtos = await db.get_produtos(guild_id=guild_id, apenas_ativos=False)
            prods_digitais = [p for p in produtos if p["tipo"] in ("digital", "ambos")]
            if not prods_digitais:
                return await interaction.response.send_message(
                    "⚠️ Nenhum produto digital cadastrado ainda. Use a opção **Criar Novo Produto** primeiro!",
                    ephemeral=True
                )
            embed = discord.Embed(
                title="📦 Abastecimento de Estoque Digital",
                description="Selecione abaixo qual produto você deseja adicionar novas chaves/linhas:",
                color=0x5865F2
            )
            view = SeletorEstoqueView(prods_digitais)
            return await interaction.response.edit_message(embed=embed, view=view)

        # 3. GERENCIAR / DELETAR PRODUTOS
        elif escolha == "gerenciar_produtos":
            produtos = await db.get_produtos(guild_id=guild_id, apenas_ativos=False)
            if not produtos:
                return await interaction.response.send_message("ℹ️ Nenhum produto cadastrado neste servidor.", ephemeral=True)

            embed = discord.Embed(
                title="📋 Gerenciamento de Produtos",
                description="Escolha um produto no menu suspenso abaixo para ver detalhes, abastecer ou excluir:",
                color=0x5865F2
            )
            view = GerenciarProdutosView(produtos)
            return await interaction.response.edit_message(embed=embed, view=view)

        # 4. GERENCIAR CUPONS
        elif escolha == "gerenciar_cupons":
            cupons = await db.get_all_cupons(guild_id=guild_id)
            embed = discord.Embed(
                title="🎟️ Gerenciador de Cupons de Desconto",
                description=f"Atualmente há **{len(cupons)}** cupom(ns) cadastrados no servidor.\n"
                            "Clique no botão para criar um novo ou selecione um para remover:",
                color=0x5865F2
            )
            for c in cupons[:5]:
                desc = f"{c['valor']}% OFF" if c["tipo"] == "percent" else f"R$ {c['valor']:.2f} OFF"
                embed.add_field(name=f"`{c['codigo']}`", value=f"Desconto: `{desc}` | Usos: `{c['usos_restantes']}`", inline=True)

            view = GerenciarCuponsView(cupons)
            return await interaction.response.edit_message(embed=embed, view=view)

        # 5. CONFIGURAR PIX MERCADO PAGO
        elif escolha == "config_pix":
            return await interaction.response.send_modal(ConfigurarPixModal())

        # 6. PUBLICAR VITRINE NO CANAL
        elif escolha == "publicar_vitrine":
            produtos = await db.get_produtos(guild_id=guild_id, apenas_ativos=True)
            if not produtos:
                return await interaction.response.send_message("⚠️ Cadastre ao menos um produto antes de publicar a vitrine!", ephemeral=True)

            embed = discord.Embed(
                title="📢 Publicação de Vitrine no Canal",
                description=f"Escolha abaixo como deseja publicar em {interaction.channel.mention}:\n\n"
                            f"• **🛍️ Item Individual:** Selecione no menu abaixo para postar um card exclusivo e direto do produto.\n"
                            f"• **📦 Apenas Digitais:** Vitrine filtrada apenas para produtos digitais (chaves/contas).\n"
                            f"• **👑 Apenas Cargos VIP:** Vitrine filtrada apenas para cargos VIPs.\n"
                            f"• **🌐 Todos os Produtos:** Catálogo geral com todos os produtos disponíveis.",
                color=0x5865F2
            )
            view = PublicarVitrineConfigView(produtos, interaction.channel)
            return await interaction.response.edit_message(embed=embed, view=view)

        # 7. RELATÓRIO FINANCEIRO
        elif escolha == "relatorio_financeiro":
            stats = await db.get_estatisticas(guild_id=guild_id)
            embed_stats = discord.Embed(
                title="📈 Relatório Financeiro da Loja",
                description=f"Desempenho de vendas em **{interaction.guild.name}**:",
                color=0x00D166,
                timestamp=datetime.now()
            )
            embed_stats.add_field(name="📅 Vendas Hoje", value=f"• Total: `{stats['vendas_hoje']} pedidos`\n• Faturamento: `R$ {stats['faturamento_hoje']:.2f}`", inline=True)
            embed_stats.add_field(name="🏆 Total Histórico", value=f"• Total: `{stats['total_vendas']} pedidos`\n• Faturamento: `R$ {stats['faturamento_total']:.2f}`", inline=True)

            if stats["top_produtos"]:
                linhas = [f"**{i}.** `{p['produto_nome']}` — {p['qtd_vendas']} vendas (`R$ {p['receita']:.2f}`)" for i, p in enumerate(stats["top_produtos"], 1)]
                embed_stats.add_field(name="🔥 Top Mais Vendidos", value="\n".join(linhas), inline=False)

            view_voltar = discord.ui.View()
            btn_voltar = discord.ui.Button(label="Voltar ao Painel", style=discord.ButtonStyle.secondary, emoji="⬅️")
            async def _cb_voltar(inter):
                e = await gerar_embed_painel_admin(inter.guild)
                v = PainelAdminView()
                await inter.response.edit_message(embed=e, view=v)
            btn_voltar.callback = _cb_voltar
            view_voltar.add_item(btn_voltar)

            return await interaction.response.edit_message(embed=embed_stats, view=view_voltar)


class PublicarItemSelect(discord.ui.Select):
    """Dropdown para selecionar qual item específico postar individualmente."""
    def __init__(self, produtos: list[dict], canal: discord.TextChannel):
        self.canal = canal
        options = []
        for p in produtos[:25]:
            emoji = p.get("emoji") or "📦"
            options.append(discord.SelectOption(
                label=p["nome"][:100],
                value=str(p["id"]),
                description=f"R$ {p['preco']:.2f} • {p['tipo'].capitalize()}",
                emoji=emoji
            ))
        super().__init__(placeholder="🛍️ Selecione um ITEM específico para postar...", options=options)

    async def callback(self, interaction: discord.Interaction):
        prod_id = int(self.values[0])
        prod = await db.get_produto_by_id(prod_id)
        if not prod:
            return await interaction.response.send_message("❌ Produto não encontrado.", ephemeral=True)

        embed = await gerar_embed_produto_individual(prod)
        view = ItemLojaView(prod)
        try:
            await self.canal.send(embed=embed, view=view)
            await interaction.response.edit_message(
                content=f"✅ Card individual do produto **{prod['nome']}** publicado com sucesso em {self.canal.mention}!",
                embed=None,
                view=None
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao enviar mensagem em {self.canal.mention}: {e}", ephemeral=True)


class PublicarVitrineConfigView(discord.ui.View):
    """Menu para escolher postar Todos os Produtos, por Grupo (Digital/Cargo) ou Item Específico."""
    def __init__(self, produtos: list[dict], canal: discord.TextChannel):
        super().__init__(timeout=300)
        self.produtos = produtos
        self.canal = canal
        if produtos:
            self.add_item(PublicarItemSelect(produtos, canal))

    @discord.ui.button(label="🌐 Todos os Produtos", style=discord.ButtonStyle.primary, emoji="🛒", row=1)
    async def btn_todos(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await gerar_embed_vitrine_produtos(self.produtos, "Catálogo Geral de Produtos")
        view = PainelLojaView(self.produtos)
        try:
            await self.canal.send(embed=embed, view=view)
            await interaction.response.edit_message(
                content=f"✅ Vitrine completa com todos os produtos enviada em {self.canal.mention}!",
                embed=None,
                view=None
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao enviar mensagem em {self.canal.mention}: {e}", ephemeral=True)

    @discord.ui.button(label="📦 Apenas Digitais", style=discord.ButtonStyle.secondary, emoji="🔑", row=1)
    async def btn_digitais(self, interaction: discord.Interaction, button: discord.ui.Button):
        prods = [p for p in self.produtos if p["tipo"] in ("digital", "ambos")]
        if not prods:
            return await interaction.response.send_message("⚠️ Nenhum produto digital cadastrado.", ephemeral=True)
        embed = await gerar_embed_vitrine_produtos(prods, "Vitrine • Produtos Digitais")
        view = PainelLojaView(prods)
        try:
            await self.canal.send(embed=embed, view=view)
            await interaction.response.edit_message(
                content=f"✅ Vitrine de produtos digitais enviada em {self.canal.mention}!",
                embed=None,
                view=None
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao enviar mensagem em {self.canal.mention}: {e}", ephemeral=True)

    @discord.ui.button(label="👑 Apenas Cargos VIP", style=discord.ButtonStyle.secondary, emoji="⭐", row=1)
    async def btn_cargos(self, interaction: discord.Interaction, button: discord.ui.Button):
        prods = [p for p in self.produtos if p["tipo"] in ("cargo", "ambos")]
        if not prods:
            return await interaction.response.send_message("⚠️ Nenhum produto de cargo VIP cadastrado.", ephemeral=True)
        embed = await gerar_embed_vitrine_produtos(prods, "Vitrine • Cargos VIP")
        view = PainelLojaView(prods)
        try:
            await self.canal.send(embed=embed, view=view)
            await interaction.response.edit_message(
                content=f"✅ Vitrine de cargos VIP enviada em {self.canal.mention}!",
                embed=None,
                view=None
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao enviar mensagem em {self.canal.mention}: {e}", ephemeral=True)

    @discord.ui.button(label="⬅️ Voltar ao Painel", style=discord.ButtonStyle.secondary, emoji="⬅️", row=2)
    async def btn_voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await gerar_embed_painel_admin(interaction.guild)
        view = PainelAdminView()
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class PainelAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AdminActionSelect())

    @discord.ui.button(label="➕ Novo Produto", style=discord.ButtonStyle.primary, emoji="✨", custom_id="btn_admin_quick_novo", row=1)
    async def btn_quick_novo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CriarProdutoModal())

    @discord.ui.button(label="📢 Publicar Vitrine", style=discord.ButtonStyle.success, emoji="🛒", custom_id="btn_admin_quick_vitrine", row=1)
    async def btn_quick_vitrine(self, interaction: discord.Interaction, button: discord.ui.Button):
        produtos = await db.get_produtos(guild_id=interaction.guild_id, apenas_ativos=True)
        if not produtos:
            return await interaction.response.send_message("⚠️ Cadastre produtos antes de publicar a vitrine.", ephemeral=True)

        embed = discord.Embed(
            title="📢 Publicação de Vitrine no Canal",
            description=f"Escolha abaixo como deseja publicar em {interaction.channel.mention}:\n\n"
                        f"• **🛍️ Item Individual:** Selecione no menu abaixo para postar um card exclusivo e direto do produto.\n"
                        f"• **📦 Apenas Digitais:** Vitrine filtrada apenas para produtos digitais (chaves/contas).\n"
                        f"• **👑 Apenas Cargos VIP:** Vitrine filtrada apenas para cargos VIPs.\n"
                        f"• **🌐 Todos os Produtos:** Catálogo geral com todos os produtos disponíveis.",
            color=0x5865F2
        )
        view = PublicarVitrineConfigView(produtos, interaction.channel)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🔄 Atualizar", style=discord.ButtonStyle.secondary, emoji="🔁", custom_id="btn_admin_quick_refresh", row=1)
    async def btn_quick_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await gerar_embed_painel_admin(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)


async def gerar_embed_painel_admin(guild: discord.Guild) -> discord.Embed:
    """Gera a mensagem do cockpit de administração da loja."""
    produtos = await db.get_produtos(guild_id=guild.id, apenas_ativos=False)
    token = await db.get_guild_mercadopago_token(guild.id)
    is_sim = gateway.is_simulation(token)
    stats = await db.get_estatisticas(guild_id=guild.id)

    status_mp = "⚡ Simulação / Teste (Dev)" if is_sim else "🟢 Mercado Pago Real (Produção)"
    token_mask = (token[:10] + "..." + token[-4:]) if (token and len(token) > 14) else "Padrão"

    embed = discord.Embed(
        title="🛠️ Central de Gerenciamento da Loja",
        description=f"Bem-vindo ao painel interativo de administração de **{guild.name}**.\n"
                    f"Selecione qualquer ação no menu abaixo para gerenciar produtos, estoque, cupons e pagamentos em tempo real.\n\n"
                    f"💡 *Para enviar a vitrine aos clientes neste canal, clique em **📢 Publicar Vitrine** ou use `/enviarpainel`.*",
        color=0x5865F2,
        timestamp=datetime.now()
    )

    embed.add_field(name="📦 Catálogo", value=f"`{len(produtos)} produto(s)`", inline=True)
    embed.add_field(name="💳 Gateway Pix", value=f"`{status_mp}`", inline=True)
    embed.add_field(name="💵 Vendas Hoje", value=f"`R$ {stats['faturamento_hoje']:.2f}` (`{stats['vendas_hoje']}`)", inline=True)

    embed.set_footer(text="Painel Administrativo Exclusivo • Selecione uma ação abaixo")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    return embed


# ==============================================================================
# COG PRINCIPAL DE ADMINISTRAÇÃO
# ==============================================================================

class AdminCog(commands.Cog, name="Administração"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==========================================================================
    # COMANDO CENTRAL: /painel (PAINEL INTERATIVO)
    # ==========================================================================
    @app_commands.command(name="painel", description="Abre a Central Interativa de Gerenciamento da Loja com menu e botões")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def cmd_painel(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Este comando só pode ser utilizado dentro de um servidor.", ephemeral=True)
        try:
            embed = await gerar_embed_painel_admin(interaction.guild)
            view = PainelAdminView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            print(f"❌ Erro ao abrir /painel: {e}")
            msg = f"❌ Ocorreu um erro ao carregar o painel: {e}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="gerenciar", description="Atalho para a Central Interativa de Gerenciamento")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def cmd_gerenciar(self, interaction: discord.Interaction):
        await self.cmd_painel(interaction)

    @app_commands.command(name="enviarpainel", description="Envia a vitrine/painel de vendas no canal para os clientes comprarem")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        canal="Canal onde o painel será enviado (opcional, padrão: canal atual)",
        item="Escolha um produto específico para postar o card individual",
        grupo="Escolha o grupo de produtos para postar"
    )
    @app_commands.choices(grupo=[
        app_commands.Choice(name="🌐 Todos os Produtos (Geral)", value="todos"),
        app_commands.Choice(name="📦 Apenas Produtos Digitais", value="digital"),
        app_commands.Choice(name="👑 Apenas Cargos VIP", value="cargo"),
        app_commands.Choice(name="✨ Apenas Produtos Mistos", value="ambos"),
    ])
    async def cmd_enviarpainel(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel = None,
        item: str = None,
        grupo: app_commands.Choice[str] = None
    ):
        await self.enviar_painel_flexivel(interaction, canal=canal, item_id_str=item, grupo_val=(grupo.value if grupo else None))

    @cmd_enviarpainel.autocomplete('item')
    async def item_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        prods = await db.get_produtos(guild_id=interaction.guild_id, apenas_ativos=True)
        choices = []
        for p in prods:
            nome_display = f"{p.get('emoji', '📦')} {p['nome']} (R$ {p['preco']:.2f})"
            if current.lower() in p["nome"].lower() or current.lower() in nome_display.lower():
                choices.append(app_commands.Choice(name=nome_display[:100], value=str(p["id"])))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name="vitrine", description="Atalho para enviar a vitrine pública de vendas no canal")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        canal="Canal onde o painel será enviado (opcional, padrão: canal atual)",
        item="Escolha um produto específico para postar o card individual",
        grupo="Escolha o grupo de produtos para postar"
    )
    @app_commands.choices(grupo=[
        app_commands.Choice(name="🌐 Todos os Produtos (Geral)", value="todos"),
        app_commands.Choice(name="📦 Apenas Produtos Digitais", value="digital"),
        app_commands.Choice(name="👑 Apenas Cargos VIP", value="cargo"),
        app_commands.Choice(name="✨ Apenas Produtos Mistos", value="ambos"),
    ])
    async def cmd_vitrine(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel = None,
        item: str = None,
        grupo: app_commands.Choice[str] = None
    ):
        await self.enviar_painel_flexivel(interaction, canal=canal, item_id_str=item, grupo_val=(grupo.value if grupo else None))

    @cmd_vitrine.autocomplete('item')
    async def vitrine_item_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self.item_autocomplete(interaction, current)

    # ==========================================================================
    # COMANDOS DIRETOS (SLASH)
    # ==========================================================================
    loja_group = app_commands.Group(name="loja", description="Gerenciamento da vitrine", default_permissions=discord.Permissions(administrator=True))

    @loja_group.command(name="enviar_painel", description="Envia o painel de vendas interativo no canal atual ou especificado")
    @app_commands.describe(
        canal="Canal onde a vitrine será postada",
        item="Escolha um produto específico para postar o card individual",
        grupo="Escolha o grupo de produtos para postar"
    )
    @app_commands.choices(grupo=[
        app_commands.Choice(name="🌐 Todos os Produtos (Geral)", value="todos"),
        app_commands.Choice(name="📦 Apenas Produtos Digitais", value="digital"),
        app_commands.Choice(name="👑 Apenas Cargos VIP", value="cargo"),
        app_commands.Choice(name="✨ Apenas Produtos Mistos", value="ambos"),
    ])
    async def loja_enviar_painel(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel = None,
        item: str = None,
        grupo: app_commands.Choice[str] = None
    ):
        await self.enviar_painel_flexivel(interaction, canal=canal, item_id_str=item, grupo_val=(grupo.value if grupo else None))

    @loja_enviar_painel.autocomplete('item')
    async def loja_item_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self.item_autocomplete(interaction, current)

    async def enviar_painel_flexivel(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel = None,
        item_id_str: str = None,
        grupo_val: str = None
    ):
        target_channel = canal or interaction.channel
        guild_id = interaction.guild_id
        produtos = await db.get_produtos(guild_id=guild_id, apenas_ativos=True)

        if not produtos:
            return await interaction.response.send_message("⚠️ Não há produtos cadastrados. Use `/painel` para criar!", ephemeral=True)

        # 1. Se informou um ITEM específico
        if item_id_str:
            try:
                prod_id = int(item_id_str)
                produto = await db.get_produto_by_id(prod_id)
            except Exception:
                produto = None

            if not produto:
                return await interaction.response.send_message("❌ Produto não encontrado ou inválido.", ephemeral=True)

            embed = await gerar_embed_produto_individual(produto)
            view = ItemLojaView(produto)
            try:
                await target_channel.send(embed=embed, view=view)
                return await interaction.response.send_message(
                    f"✅ Card individual do produto **{produto['nome']}** enviado com sucesso em {target_channel.mention}!",
                    ephemeral=True
                )
            except Exception as e:
                return await interaction.response.send_message(f"❌ Erro ao enviar mensagem em {target_channel.mention}: {e}", ephemeral=True)

        # 2. Se informou um GRUPO específico
        if grupo_val and grupo_val != "todos":
            prods_filtrados = [p for p in produtos if p["tipo"] in (grupo_val, "ambos")]
            if not prods_filtrados:
                return await interaction.response.send_message(f"⚠️ Não há produtos cadastrados no grupo `{grupo_val}`.", ephemeral=True)

            nomes_grupos = {
                "digital": "Vitrine • Produtos Digitais",
                "cargo": "Vitrine • Cargos VIP",
                "ambos": "Vitrine • Produtos Mistos"
            }
            titulo = nomes_grupos.get(grupo_val, f"Vitrine • {grupo_val.capitalize()}")
            embed = await gerar_embed_vitrine_produtos(prods_filtrados, titulo)
            view = PainelLojaView(prods_filtrados)
            try:
                await target_channel.send(embed=embed, view=view)
                return await interaction.response.send_message(
                    f"✅ Vitrine do grupo `{grupo_val}` enviada com sucesso em {target_channel.mention}!",
                    ephemeral=True
                )
            except Exception as e:
                return await interaction.response.send_message(f"❌ Erro ao enviar mensagem em {target_channel.mention}: {e}", ephemeral=True)

        # 3. Se escolheu "todos" explicitamente
        if grupo_val == "todos":
            embed = await gerar_embed_vitrine_produtos(produtos, "Catálogo Geral de Produtos")
            view = PainelLojaView(produtos)
            try:
                await target_channel.send(embed=embed, view=view)
                return await interaction.response.send_message(
                    f"✅ Catálogo completo enviado com sucesso em {target_channel.mention}!",
                    ephemeral=True
                )
            except Exception as e:
                return await interaction.response.send_message(f"❌ Erro ao enviar mensagem em {target_channel.mention}: {e}", ephemeral=True)

        # 4. Se não especificou nem item nem grupo, abre o menu interativo de escolha!
        embed = discord.Embed(
            title="📢 Publicação de Vitrine no Canal",
            description=f"Escolha abaixo como deseja publicar em {target_channel.mention}:\n\n"
                        f"• **🛍️ Item Individual:** Selecione no menu abaixo para postar um card exclusivo e direto do produto.\n"
                        f"• **📦 Apenas Digitais:** Vitrine filtrada apenas para produtos digitais (chaves/contas).\n"
                        f"• **👑 Apenas Cargos VIP:** Vitrine filtrada apenas para cargos VIPs.\n"
                        f"• **🌐 Todos os Produtos:** Catálogo geral com todos os produtos disponíveis.",
            color=0x5865F2
        )
        view = PublicarVitrineConfigView(produtos, target_channel)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # GRUPO /configurar
    config_group = app_commands.Group(name="configurar", description="Configurações gerais", default_permissions=discord.Permissions(administrator=True))

    @config_group.command(name="canais", description="Configura os canais de logs, avaliações e categoria de carrinhos")
    async def config_canais(self, interaction: discord.Interaction,
                            canal_logs: discord.TextChannel = None,
                            canal_avaliacoes: discord.TextChannel = None,
                            categoria_carrinhos: discord.CategoryChannel = None):
        gid = interaction.guild_id
        respostas = []
        if canal_logs:
            await db.set_config("canal_logs_id", str(canal_logs.id), guild_id=gid)
            respostas.append(f"• Canal de Logs: {canal_logs.mention}")
        if canal_avaliacoes:
            await db.set_config("canal_avaliacoes_id", str(canal_avaliacoes.id), guild_id=gid)
            respostas.append(f"• Canal de Avaliações: {canal_avaliacoes.mention}")
        if categoria_carrinhos:
            await db.set_config("categoria_carrinhos_id", str(categoria_carrinhos.id), guild_id=gid)
            respostas.append(f"• Categoria de Carrinhos: `{categoria_carrinhos.name}`")

        if not respostas:
            return await interaction.response.send_message("⚠️ Nenhum canal foi selecionado para alteração.", ephemeral=True)

        embed = discord.Embed(title="⚙️ Canais Atualizados!", description="\n".join(respostas), color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    mp_group = app_commands.Group(name="mercadopago", description="Gerenciamento do Pix deste Servidor", parent=config_group)

    @mp_group.command(name="definir", description="Define o Access Token do Mercado Pago deste servidor")
    async def mp_definir(self, interaction: discord.Interaction, token: str):
        token_clean = token.strip()
        if not token_clean.startswith("APP_USR-") and not token_clean.startswith("TEST-"):
            return await interaction.response.send_message("❌ Token inválido! Deve iniciar com `APP_USR-`.", ephemeral=True)

        await db.set_guild_mercadopago_token(interaction.guild_id, token_clean)
        token_mascarado = token_clean[:10] + "..." + token_clean[-4:]
        embed = discord.Embed(
            title="💳 Mercado Pago Configurado!",
            description=f"🔒 **Token Ativo:** `{token_mascarado}`\nTodas as vendas cairão diretamente na sua conta bancária!",
            color=0x00D166
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @mp_group.command(name="remover", description="Remove o token customizado deste servidor")
    async def mp_remover(self, interaction: discord.Interaction):
        await db.remove_guild_mercadopago_token(interaction.guild_id)
        await interaction.response.send_message("🗑️ Token customizado removido com sucesso.", ephemeral=True)

    @config_group.command(name="gateway", description="Verifica o status atual do gateway de pagamento")
    async def config_gateway(self, interaction: discord.Interaction):
        token = await db.get_guild_mercadopago_token(interaction.guild_id)
        is_sim = gateway.is_simulation(token)
        modo = "⚡ Modo Simulação / Teste (Dev)" if is_sim else "🟢 Mercado Pago Oficial Ativo (Produção)"
        token_mask = (token[:10] + "..." + token[-4:]) if (token and len(token) > 12) else "Não configurado"

        embed = discord.Embed(
            title=f"💳 Gateway de Pagamento • {interaction.guild.name}",
            description=f"**Status Atual:** {modo}\n**Token:** `{token_mask}`",
            color=0x00D166 if not is_sim else 0xFEE75C
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="estatisticas", description="Painel financeiro de vendas e faturamento da loja")
    @app_commands.default_permissions(administrator=True)
    async def estatisticas(self, interaction: discord.Interaction):
        stats = await db.get_estatisticas(guild_id=interaction.guild_id)
        embed = discord.Embed(
            title="📈 Dashboard Financeiro",
            description=f"Resumo consolidado das vendas em **{interaction.guild.name}**.",
            color=0x00D166,
            timestamp=datetime.now()
        )
        embed.add_field(name="📅 Vendas Hoje", value=f"• Total: `{stats['vendas_hoje']}`\n• Faturamento: `R$ {stats['faturamento_hoje']:.2f}`", inline=True)
        embed.add_field(name="🏆 Histórico Geral", value=f"• Total: `{stats['total_vendas']}`\n• Faturamento: `R$ {stats['faturamento_total']:.2f}`", inline=True)
        if stats["top_produtos"]:
            linhas = [f"**{i}.** `{p['produto_nome']}` — {p['qtd_vendas']} vendas (`R$ {p['receita']:.2f}`)" for i, p in enumerate(stats["top_produtos"], 1)]
            embed.add_field(name="🔥 Top Mais Vendidos", value="\n".join(linhas), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
