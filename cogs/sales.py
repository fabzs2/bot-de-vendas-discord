import io
import os
import uuid
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

import database as db
from payments import gateway, generate_qr_code_image

# ==============================================================================
# VIEW DE AVALIAÇÃO DO CLIENTE
# ==============================================================================
class ReviewModal(discord.ui.Modal, title="⭐ Avaliar Sua Compra"):
    estrelas = discord.ui.TextInput(
        label="Sua Nota (1 a 5)",
        placeholder="Digite um número de 1 a 5",
        min_length=1,
        max_length=1,
        default="5"
    )
    comentario = discord.ui.TextInput(
        label="Seu Comentário ou Feedback",
        style=discord.TextStyle.paragraph,
        placeholder="O que achou da entrega rápida e do atendimento?",
        max_length=500,
        required=False
    )

    def __init__(self, pedido_codigo: str, produto_nome: str):
        super().__init__()
        self.pedido_codigo = pedido_codigo
        self.produto_nome = produto_nome

    async def on_submit(self, interaction: discord.Interaction):
        try:
            nota = int(self.estrelas.value)
            if nota < 1 or nota > 5:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ Por favor, digite uma nota válida entre 1 e 5.", ephemeral=True)
            return

        coment = self.comentario.value or "Sem comentário adicional."
        guild_id = interaction.guild_id
        await db.add_avaliacao(self.pedido_codigo, interaction.user.id, interaction.user.name, nota, coment, guild_id=guild_id)

        # Envia no canal público de avaliações do servidor se configurado
        canal_aval_id = await db.get_config("canal_avaliacoes_id", guild_id=guild_id)
        if canal_aval_id:
            try:
                canal_aval = interaction.guild.get_channel(int(canal_aval_id))
                if canal_aval:
                    estrelas_str = "⭐" * nota
                    embed_review = discord.Embed(
                        title=f"{estrelas_str} Nova Avaliação!",
                        description=f"**Cliente:** {interaction.user.mention}\n"
                                    f"**Produto:** `{self.produto_nome}`\n"
                                    f"**Pedido:** `#{self.pedido_codigo}`\n\n"
                                    f"💬 **Feedback:**\n*{coment}*",
                        color=discord.Color.gold(),
                        timestamp=datetime.now()
                    )
                    embed_review.set_thumbnail(url=interaction.user.display_avatar.url)
                    embed_review.set_footer(text="Loja Automática • Compra Verificada")
                    await canal_aval.send(embed=embed_review)
            except Exception as e:
                print(f"[Erro ao postar avaliação] {e}")

        await interaction.response.send_message("💖 Muito obrigado pelo seu feedback! Sua avaliação foi registrada.", ephemeral=True)


class ReviewButtonView(discord.ui.View):
    def __init__(self, pedido_codigo: str, produto_nome: str):
        super().__init__(timeout=None)
        self.pedido_codigo = pedido_codigo
        self.produto_nome = produto_nome

    @discord.ui.button(label="Avaliar Atendimento", style=discord.ButtonStyle.primary, emoji="⭐", custom_id="btn_avaliar_compra")
    async def avaliar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReviewModal(self.pedido_codigo, self.produto_nome))


# ==============================================================================
# MODAL DE CUPOM DE DESCONTO
# ==============================================================================
class CupomModal(discord.ui.Modal, title="🎟️ Inserir Cupom de Desconto"):
    codigo = discord.ui.TextInput(
        label="Código do Cupom",
        placeholder="Ex: PROMO10, BEMVINDO",
        max_length=30
    )

    def __init__(self, carrinho_view):
        super().__init__()
        self.carrinho_view = carrinho_view

    async def on_submit(self, interaction: discord.Interaction):
        codigo_cupom = self.codigo.value.strip().upper()
        cupom = await db.get_cupom(codigo_cupom, guild_id=interaction.guild_id)

        if not cupom:
            await interaction.response.send_message("❌ Cupom inválido, expirado ou esgotado.", ephemeral=True)
            return

        self.carrinho_view.cupom_aplicado = cupom
        await self.carrinho_view.atualizar_mensagem_carrinho(interaction)


# ==============================================================================
# VIEW INTERNA DO CARRINHO (GERENCIAMENTO DE QUANTIDADE, CUPOM E PAGAMENTO)
# ==============================================================================
class CarrinhoManageView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.Member, produto: dict):
        super().__init__(timeout=900) # 15 minutos
        self.bot = bot
        self.user = user
        self.produto = produto
        self.quantidade = 1
        self.cupom_aplicado = None
        self.message = None
        self.pagamento_iniciado = False
        self.pedido_codigo = f"PED-{uuid.uuid4().hex[:8].upper()}"
        self.polling_task = None

    def calcular_total(self) -> float:
        total = self.produto["preco"] * self.quantidade
        if self.cupom_aplicado:
            if self.cupom_aplicado["tipo"] == "percent":
                desconto = total * (self.cupom_aplicado["valor"] / 100.0)
                total = max(0.50, total - desconto)
            else:
                total = max(0.50, total - self.cupom_aplicado["valor"])
        return round(total, 2)

    def gerar_embed_carrinho(self, estoque_disp: int) -> discord.Embed:
        total = self.calcular_total()
        embed = discord.Embed(
            title=f"🛒 Carrinho de Compras • #{self.pedido_codigo}",
            description=f"Olá, {self.user.mention}! Você está adquirindo um produto exclusivo com **entrega 100% automatizada**.\n"
                        f"Revise seu pedido abaixo antes de prosseguir para o Pix.",
            color=0x5865F2,
            timestamp=datetime.now()
        )

        tipo_map = {
            "cargo": "👑 Cargo no Discord (VIP)",
            "digital": "🔑 Item Digital (Chave/Licença/Conta)",
            "ambos": "🎁 Combo Especial (Cargo + Item Digital)"
        }
        tipo_str = tipo_map.get(self.produto["tipo"], self.produto["tipo"].capitalize())

        embed.add_field(name="📦 Produto", value=f"**{self.produto.get('emoji', '📦')} {self.produto['nome']}**", inline=False)
        embed.add_field(name="📝 Detalhes", value=f"{self.produto.get('descricao', 'Sem descrição.')}", inline=False)
        embed.add_field(name="ℹ️ Formato de Entrega", value=f"`{tipo_str}`", inline=True)
        embed.add_field(name="💵 Valor Unitário", value=f"`R$ {self.produto['preco']:.2f}`", inline=True)
        embed.add_field(name="🔢 Quantidade", value=f"`{self.quantidade} unidade(s)`", inline=True)

        if self.produto["tipo"] in ("digital", "ambos"):
            embed.add_field(name="📊 Estoque Disponível", value=f"`{estoque_disp} item(ns)`", inline=True)

        if self.cupom_aplicado:
            c_desc = f"{self.cupom_aplicado['valor']}% OFF" if self.cupom_aplicado['tipo'] == 'percent' else f"R$ {self.cupom_aplicado['valor']:.2f} OFF"
            embed.add_field(name="🎟️ Cupom Ativo", value=f"`{self.cupom_aplicado['codigo']}` ({c_desc})", inline=True)

        embed.add_field(name="💳 Total a Pagar", value=f"```fix\nR$ {total:.2f}\n```", inline=False)
        embed.set_footer(text="⏱️ Este carrinho expirará automaticamente em 15 minutos de inatividade.")
        return embed

    async def atualizar_mensagem_carrinho(self, interaction: discord.Interaction):
        estoque_disp = await db.get_estoque_count(self.produto["id"]) if self.produto["tipo"] in ("digital", "ambos") else 999
        embed = self.gerar_embed_carrinho(estoque_disp)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="-1", style=discord.ButtonStyle.secondary, emoji="➖", row=0)
    async def btn_diminuir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Este carrinho pertence a outro cliente.", ephemeral=True)
        if self.pagamento_iniciado:
            return await interaction.response.send_message("⚠️ O pagamento já foi gerado.", ephemeral=True)

        if self.quantidade > 1:
            self.quantidade -= 1
            await self.atualizar_mensagem_carrinho(interaction)
        else:
            await interaction.response.send_message("⚠️ A quantidade mínima é 1 unidade.", ephemeral=True)

    @discord.ui.button(label="+1", style=discord.ButtonStyle.secondary, emoji="➕", row=0)
    async def btn_aumentar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Este carrinho pertence a outro cliente.", ephemeral=True)
        if self.pagamento_iniciado:
            return await interaction.response.send_message("⚠️ O pagamento já foi gerado.", ephemeral=True)

        # Se for cargo exclusivo, quantidade maior que 1 não faz sentido
        if self.produto["tipo"] == "cargo":
            return await interaction.response.send_message("ℹ️ O produto é um Cargo VIP individual (limite de 1 por cliente).", ephemeral=True)

        # Checa estoque para produtos digitais
        if self.produto["tipo"] in ("digital", "ambos"):
            estoque_disp = await db.get_estoque_count(self.produto["id"])
            if self.quantidade + 1 > estoque_disp:
                return await interaction.response.send_message(f"⚠️ Limite de estoque atingido! Há apenas {estoque_disp} unidade(s) disponíveis.", ephemeral=True)

        self.quantidade += 1
        await self.atualizar_mensagem_carrinho(interaction)

    @discord.ui.button(label="Aplicar Cupom", style=discord.ButtonStyle.primary, emoji="🎟️", row=0)
    async def btn_cupom(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Este carrinho pertence a outro cliente.", ephemeral=True)
        if self.pagamento_iniciado:
            return await interaction.response.send_message("⚠️ O Pix já foi gerado para este pedido.", ephemeral=True)

        await interaction.response.send_modal(CupomModal(self))

    @discord.ui.button(label="Pagar com Pix", style=discord.ButtonStyle.success, emoji="⚡", row=1)
    async def btn_ir_pagamento(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Este carrinho pertence a outro cliente.", ephemeral=True)
        if self.pagamento_iniciado:
            return await interaction.response.send_message("⚠️ O Pix já está aberto e aguardando confirmação!", ephemeral=True)

        # Validação final de estoque
        if self.produto["tipo"] in ("digital", "ambos"):
            estoque_disp = await db.get_estoque_count(self.produto["id"])
            if estoque_disp < self.quantidade:
                return await interaction.response.send_message(
                    f"❌ Infelizmente o estoque acabou enquanto você escolhia. Restam apenas {estoque_disp} unidade(s).",
                    ephemeral=True
                )

        await interaction.response.defer()
        self.pagamento_iniciado = True
        total = self.calcular_total()

        # Busca o token Mercado Pago específico deste servidor (Multi-tenant)
        guild_mp_token = await db.get_guild_mercadopago_token(interaction.guild_id)

        # Cria a cobrança Pix
        pix_info = await gateway.create_pix(
            amount=total,
            description=f"Compra {self.produto['nome']}",
            payer_name=self.user.name,
            order_id=self.pedido_codigo,
            access_token=guild_mp_token
        )

        pix_id = pix_info["id"]
        copia_cola = pix_info.get("copia_cola", "")
        cupom_cod = self.cupom_aplicado["codigo"] if self.cupom_aplicado else None

        # Salva no banco de dados com guild_id
        await db.criar_pedido(
            codigo_pedido=self.pedido_codigo,
            user_id=self.user.id,
            user_name=str(self.user),
            produto_id=self.produto["id"],
            produto_nome=self.produto["nome"],
            quantidade=self.quantidade,
            valor_unitario=self.produto["preco"],
            valor_total=total,
            cupom_codigo=cupom_cod,
            pix_id=pix_id,
            pix_copia_cola=copia_cola,
            canal_id=interaction.channel.id,
            guild_id=interaction.guild_id
        )

        # Gera a imagem do QR Code em memória
        qr_buffer = generate_qr_code_image(copia_cola)
        qr_file = discord.File(qr_buffer, filename="pix_qrcode.png")

        embed_pix = discord.Embed(
            title=f"💠 Pagamento Pix • {self.produto['nome']}",
            description=f"Escaneie o QR Code abaixo no app do seu banco ou utilize o **Pix Copia e Cola**.\n\n"
                        f"⏳ O sistema identifica seu pagamento **automaticamente em segundos**!",
            color=0x00D166,
            timestamp=datetime.now()
        )
        embed_pix.add_field(name="💰 Valor a Pagar", value=f"```fix\nR$ {total:.2f}\n```", inline=True)
        embed_pix.add_field(name="🆔 Código do Pedido", value=f"`#{self.pedido_codigo}`", inline=True)
        embed_pix.add_field(
            name="📋 Pix Copia e Cola (Clique para copiar)",
            value=f"```{copia_cola}```",
            inline=False
        )
        embed_pix.set_image(url="attachment://pix_qrcode.png")
        embed_pix.set_footer(text="Após pagar no seu banco, aguarde a liberação automática ou clique em 'Verificar Pagamento'.")

        view_pag = PixPaymentView(
            bot=self.bot,
            user=self.user,
            produto=self.produto,
            pedido_codigo=self.pedido_codigo,
            pix_id=pix_id,
            quantidade=self.quantidade,
            cupom=self.cupom_aplicado,
            access_token=guild_mp_token,
            valor_total=total
        )
        
        # Limpa view anterior e envia o Pix
        msg = await interaction.channel.send(embed=embed_pix, file=qr_file, view=view_pag)
        view_pag.message = msg

        # Inicia polling de verificação em background
        self.polling_task = asyncio.create_task(view_pag.iniciar_polling_pagamento(interaction.channel))

    @discord.ui.button(label="Cancelar Carrinho", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def btn_cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Você não tem permissão para cancelar este carrinho.", ephemeral=True)

        await db.marcar_pedido_cancelado(self.pedido_codigo, "cancelado")
        await interaction.response.send_message("🗑️ **Carrinho cancelado.** Este canal será excluído em 5 segundos...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason="Carrinho cancelado pelo usuário")
        except Exception:
            pass


# ==============================================================================
# VIEW DE CONTROLE DO PIX (POLLING, CHECAGEM E SIMULAÇÃO)
# ==============================================================================
class PixPaymentView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.Member, produto: dict, pedido_codigo: str, pix_id: str,
                 quantidade: int, cupom: dict = None, access_token: str = None, valor_total: float = None):
        super().__init__(timeout=900)
        self.bot = bot
        self.user = user
        self.produto = produto
        self.pedido_codigo = pedido_codigo
        self.pix_id = pix_id
        self.quantidade = quantidade
        self.cupom = cupom
        self.access_token = access_token
        self.valor_total = valor_total if valor_total is not None else (produto["preco"] * quantidade)
        self.is_finalizado = False
        self.message = None

    async def processar_entrega(self, channel: discord.TextChannel):
        """Executa a entrega atômica do produto (cargo e/ou item digital)."""
        if self.is_finalizado:
            return
        self.is_finalizado = True
        self.stop()

        # 1. Decrementa uso do cupom se foi usado
        if self.cupom:
            await db.decrementar_cupom(self.cupom["codigo"])

        # 2. Retira itens do estoque se for digital ou ambos
        itens_entregues = []
        if self.produto["tipo"] in ("digital", "ambos"):
            itens_entregues = await db.consumir_estoque(self.produto["id"], self.quantidade)
        
        entregue_txt = "\n".join(itens_entregues) if itens_entregues else "Cargo VIP Ativado"
        await db.marcar_pedido_pago(self.pedido_codigo, entregue_txt)

        # 3. Entrega de Cargo no Discord
        cargo_entregue = False
        if self.produto["tipo"] in ("cargo", "ambos") and self.produto.get("cargo_id"):
            try:
                cargo = channel.guild.get_role(int(self.produto["cargo_id"]))
                if cargo:
                    await self.user.add_roles(cargo, reason=f"Compra aprovada pedido #{self.pedido_codigo}")
                    cargo_entregue = True
            except Exception as e:
                print(f"[Erro ao entregar cargo] {e}")

        # 4. Envio de Mensagem Direta (DM) para o cliente
        embed_dm = discord.Embed(
            title="🎉 Pagamento Aprovado • Produto Entregue!",
            description=f"Obrigado por comprar conosco no servidor **{channel.guild.name}**!\n\n"
                        f"📦 **Produto:** `{self.produto['nome']}`\n"
                        f"🔢 **Quantidade:** `x{self.quantidade}`\n"
                        f"🆔 **Pedido:** `#{self.pedido_codigo}`",
            color=0x00D166,
            timestamp=datetime.now()
        )

        if cargo_entregue:
            embed_dm.add_field(name="👑 Cargo Entregue", value=f"O cargo <@&{self.produto['cargo_id']}> foi adicionado ao seu perfil!", inline=False)

        if itens_entregues:
            conteudo_bloco = "\n".join(f"• `{item}`" for item in itens_entregues)
            embed_dm.add_field(name="🔑 Seu(s) Item(ns) / Chaves", value=conteudo_bloco, inline=False)

        embed_dm.set_footer(text="Guarde este comprovante • Obrigado pela preferência!")

        dm_enviada = False
        try:
            view_aval = ReviewButtonView(self.pedido_codigo, self.produto["nome"])
            await self.user.send(embed=embed_dm, view=view_aval)
            dm_enviada = True
        except discord.Forbidden:
            dm_enviada = False

        # 5. Notificação no canal do carrinho
        embed_canal = discord.Embed(
            title="✅ Pagamento Aprovado com Sucesso!",
            description=f"Parabéns {self.user.mention}! Seu pagamento foi confirmado pelo sistema.",
            color=0x00D166
        )
        if cargo_entregue:
            embed_canal.add_field(name="👑 Cargo Adicionado", value=f"O cargo <@&{self.produto['cargo_id']}> já está ativo no seu perfil!", inline=False)

        if dm_enviada:
            embed_canal.add_field(name="📥 Entrega na DM", value="Enviamos todos os dados do seu produto diretamente no seu privado (DM)!", inline=False)
        else:
            # Fallback se a DM estiver fechada
            embed_canal.add_field(
                name="⚠️ DM Bloqueada - Entrega Aqui",
                value="Sua DM está desativada! Veja abaixo o seu produto:\n" + ("\n".join(f"`{i}`" for i in itens_entregues) if itens_entregues else "Cargo VIP Ativado"),
                inline=False
            )

        view_aval_canal = ReviewButtonView(self.pedido_codigo, self.produto["nome"])
        await channel.send(embed=embed_canal, view=view_aval_canal)

        # 6. Log no canal administrativo de vendas do servidor
        canal_logs_id = await db.get_config("canal_logs_id", guild_id=channel.guild.id)
        if canal_logs_id:
            try:
                canal_logs = channel.guild.get_channel(int(canal_logs_id))
                if canal_logs:
                    embed_log = discord.Embed(
                        title="💰 Nova Venda Realizada!",
                        color=0x00D166,
                        timestamp=datetime.now()
                    )
                    embed_log.add_field(name="👤 Comprador", value=f"{self.user.mention} (`{self.user.id}`)", inline=True)
                    embed_log.add_field(name="📦 Produto", value=f"`{self.produto['nome']}` (x{self.quantidade})", inline=True)
                    embed_log.add_field(name="💵 Total", value=f"`R$ {self.valor_total:.2f}`", inline=True)
                    embed_log.add_field(name="🆔 Pedido", value=f"`#{self.pedido_codigo}`", inline=True)
                    embed_log.set_thumbnail(url=self.user.display_avatar.url)
                    await canal_logs.send(embed=embed_log)
            except Exception as e:
                print(f"[Erro ao registrar log de venda] {e}")

        # 7. Finalização do canal com contagem regressiva
        await channel.send("🏁 **Atendimento concluído com sucesso.** Este canal será fechado em 45 segundos.")
        await asyncio.sleep(45)
        try:
            await channel.delete(reason="Compra finalizada")
        except Exception:
            pass

    async def iniciar_polling_pagamento(self, channel: discord.TextChannel):
        """Loop assíncrono que consulta o status do Pix a cada 7 segundos."""
        for _ in range(120): # 120 * 7s = 14 minutos
            if self.is_finalizado:
                break
            await asyncio.sleep(7)
            status = await gateway.check_status(self.pix_id, access_token=self.access_token)
            if status == "approved":
                await self.processar_entrega(channel)
                break
            elif status in ("cancelled", "rejected"):
                await db.marcar_pedido_cancelado(self.pedido_codigo, "expirado")
                await channel.send("❌ O pagamento Pix foi cancelado ou expirou. O carrinho será fechado.")
                await asyncio.sleep(5)
                try:
                    await channel.delete(reason="Pix cancelado")
                except Exception:
                    pass
                break

    @discord.ui.button(label="Verificar Pagamento", style=discord.ButtonStyle.primary, emoji="🔄", row=0)
    async def btn_verificar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        status = await gateway.check_status(self.pix_id, access_token=self.access_token)
        if status == "approved":
            await interaction.followup.send("✅ Pagamento identificado! Entregando seu produto agora...", ephemeral=True)
            await self.processar_entrega(interaction.channel)
        else:
            await interaction.followup.send("⏳ O pagamento ainda não foi identificado pelo banco. Se já pagou, aguarde alguns segundos.", ephemeral=True)

    @discord.ui.button(label="Simular Aprovação (Teste/Dev)", style=discord.ButtonStyle.success, emoji="⚡", row=0)
    async def btn_simular_aprovacao(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Permite que administradores ou qualquer usuário no modo simulação aprovem o pagamento para testes."""
        # Se estiver em modo oficial, apenas administradores podem forçar a aprovação de teste
        if not gateway.is_simulation(self.access_token) and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Apenas administradores podem forçar a aprovação manual.", ephemeral=True)

        await interaction.response.send_message("⚡ **Aprovação de simulação ativada!** Processando entrega...", ephemeral=True)
        await self.processar_entrega(interaction.channel)

    @discord.ui.button(label="Cancelar Pedido", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def btn_cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Você não tem permissão para cancelar.", ephemeral=True)

        self.is_finalizado = True
        self.stop()
        await db.marcar_pedido_cancelado(self.pedido_codigo, "cancelado")
        await interaction.response.send_message("🗑️ Pedido cancelado. Fechando canal...")
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete(reason="Cancelado pelo usuário")
        except Exception:
            pass


# ==============================================================================
# VIEW DO PAINEL PRINCIPAL DA LOJA (VITRINE COM SELECT MENU E BOTÕES)
# ==============================================================================
class ProductSelect(discord.ui.Select):
    def __init__(self, produtos: list[dict]):
        options = []
        for p in produtos[:25]:
            emoji = p.get("emoji") or "📦"
            desc = f"R$ {p['preco']:.2f} • {p.get('descricao', '')[:50]}"
            options.append(discord.SelectOption(
                label=p["nome"][:100],
                value=str(p["id"]),
                description=desc[:100],
                emoji=emoji
            ))
        
        super().__init__(
            placeholder="🛒 Selecione um produto para comprar...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_produto_loja"
        )

    async def callback(self, interaction: discord.Interaction):
        produto_id = int(self.values[0])
        produto = await db.get_produto_by_id(produto_id)
        if not produto or not produto.get("ativo"):
            return await interaction.response.send_message("❌ Este produto não está mais disponível.", ephemeral=True)

        await abrir_carrinho_usuario(interaction, produto)


class PainelLojaView(discord.ui.View):
    def __init__(self, produtos: list[dict] = None):
        super().__init__(timeout=None)
        if produtos:
            self.add_item(ProductSelect(produtos))

    @discord.ui.button(label="Comprar Produto em Destaque", style=discord.ButtonStyle.primary, emoji="🛒", custom_id="btn_comprar_destaque")
    async def btn_destaque(self, interaction: discord.Interaction, button: discord.ui.Button):
        produtos = await db.get_produtos(guild_id=interaction.guild_id, apenas_ativos=True)
        if not produtos:
            return await interaction.response.send_message("❌ Nenhum produto ativo na loja no momento.", ephemeral=True)
        await abrir_carrinho_usuario(interaction, produtos[0])

    @discord.ui.button(label="Ver Estoque", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="btn_ver_estoque_loja")
    async def btn_estoque(self, interaction: discord.Interaction, button: discord.ui.Button):
        produtos = await db.get_produtos(guild_id=interaction.guild_id, apenas_ativos=True)
        if not produtos:
            return await interaction.response.send_message("ℹ️ Nenhum produto cadastrado no momento.", ephemeral=True)

        embed = discord.Embed(
            title="📊 Estoque Disponível em Tempo Real",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        for p in produtos:
            if p["tipo"] in ("digital", "ambos"):
                qtd = await db.get_estoque_count(p["id"])
                status_txt = f"`{qtd} unidade(s)`" if qtd > 0 else "🔴 *Esgotado*"
            else:
                status_txt = "🟢 *Disponível Imediato (Cargo)*"
            embed.add_field(name=f"{p.get('emoji', '📦')} {p['nome']}", value=f"Preço: `R$ {p['preco']:.2f}`\nEstoque: {status_txt}", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==============================================================================
# FUNÇÃO CENTRAL DE CRIAÇÃO DO CANAL DO CARRINHO (TICKET)
# ==============================================================================
async def abrir_carrinho_usuario(interaction: discord.Interaction, produto: dict):
    guild = interaction.guild
    membro = interaction.user

    # Verifica se o produto requer estoque digital e se está esgotado
    if produto["tipo"] in ("digital", "ambos"):
        estoque_disp = await db.get_estoque_count(produto["id"])
        if estoque_disp <= 0:
            return await interaction.response.send_message("🔴 Desculpe, este produto está temporariamente **esgotado**!", ephemeral=True)

    # Verifica se o usuário já possui um canal de carrinho aberto no servidor
    prefixo_canal = f"carrinho-{membro.name.lower()[:15]}"
    canal_existente = discord.utils.find(lambda c: c.name.startswith(prefixo_canal), guild.text_channels)
    if canal_existente:
        return await interaction.response.send_message(
            f"⚠️ Você já possui um carrinho aberto em {canal_existente.mention}! Finalize ou cancele o anterior antes de abrir um novo.",
            ephemeral=True
        )

    await interaction.response.send_message("⏳ Abrindo seu carrinho de compras com segurança...", ephemeral=True)

    # Categoria configurada para este servidor
    cat_id = await db.get_config("categoria_carrinhos_id", guild_id=guild.id)
    categoria = guild.get_channel(int(cat_id)) if cat_id else interaction.channel.category

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        membro: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
    }

    nome_canal = f"carrinho-{membro.name.lower()[:15]}"
    canal_carrinho = await guild.create_text_channel(name=nome_canal, category=categoria, overwrites=overwrites)

    # View interativa do carrinho
    carrinho_view = CarrinhoManageView(interaction.client, membro, produto)
    estoque_disp = await db.get_estoque_count(produto["id"]) if produto["tipo"] in ("digital", "ambos") else 999
    embed = carrinho_view.gerar_embed_carrinho(estoque_disp)

    msg = await canal_carrinho.send(
        content=f"🔔 {membro.mention}, seu carrinho foi criado!",
        embed=embed,
        view=carrinho_view
    )
    carrinho_view.message = msg

    await interaction.followup.send(f"✅ Seu carrinho foi aberto com sucesso: {canal_carrinho.mention}", ephemeral=True)


class ItemLojaView(discord.ui.View):
    """View persistente do card individual de um produto com botão direto de compra e consulta de estoque."""
    def __init__(self, produto: dict):
        super().__init__(timeout=None)
        prod_id = produto["id"]
        self.add_item(discord.ui.Button(
            label=f"Comprar • R$ {produto['preco']:.2f}",
            style=discord.ButtonStyle.success,
            emoji="🛒",
            custom_id=f"buy_item_{prod_id}"
        ))
        if produto["tipo"] in ("digital", "ambos"):
            self.add_item(discord.ui.Button(
                label="Ver Estoque",
                style=discord.ButtonStyle.secondary,
                emoji="📊",
                custom_id=f"stock_item_{prod_id}"
            ))


async def gerar_embed_produto_individual(produto: dict) -> discord.Embed:
    """Gera um embed elegante e dedicado para a vitrine individual de um produto."""
    emoji = produto.get("emoji") or "📦"
    preco = produto["preco"]
    tipo = produto["tipo"]

    if tipo in ("digital", "ambos"):
        qtd = await db.get_estoque_count(produto["id"])
        status_estoque = f"`{qtd} unidade(s)` disponível(is)" if qtd > 0 else "🔴 *Temporariamente Esgotado*"
    else:
        status_estoque = "🟢 *Ativação Automática (Cargo VIP)*"

    embed = discord.Embed(
        title=f"{emoji} {produto['nome']} • R$ {preco:.2f}",
        description=f"{produto.get('descricao') or 'Sem descrição definida.'}\n\n"
                    f"💎 **Entrega 100% Automática via Pix** com aprovação instantânea!\n"
                    f"🔒 **Atendimento Seguro:** Seu carrinho é aberto em canal privado exclusivo.",
        color=0x5865F2,
        timestamp=datetime.now()
    )

    embed.add_field(name="💰 Valor Unitário", value=f"`R$ {preco:.2f}`", inline=True)
    embed.add_field(name="📦 Estoque", value=status_estoque, inline=True)
    embed.add_field(name="🏷️ Tipo", value=f"`{tipo.capitalize()}`", inline=True)
    embed.set_footer(text="Clique no botão verde abaixo para comprar instantaneamente!")
    return embed


async def gerar_embed_vitrine_produtos(produtos: list[dict], titulo: str = "Catálogo de Produtos") -> discord.Embed:
    """Gera o embed de vitrine para um grupo de produtos ou para o catálogo geral."""
    embed = discord.Embed(
        title=f"🛒 {titulo}",
        description="Seja muito bem-vindo(a) à nossa vitrine oficial!\n"
                    "Escolha um dos produtos abaixo para abrir seu carrinho seguro e comprar com **Pix Automático**.\n\n"
                    "💎 *Qualidade garantida, entrega imediata e suporte ágil.*",
        color=0x5865F2,
        timestamp=datetime.now()
    )
    for p in produtos[:25]:
        emoji = p.get("emoji") or "📦"
        if p["tipo"] in ("digital", "ambos"):
            qtd = await db.get_estoque_count(p["id"])
            qtd_info = f"📦 `{qtd} em estoque`" if qtd > 0 else "🔴 *Esgotado*"
        else:
            qtd_info = "👑 *Cargo Automático*"
        embed.add_field(name=f"{emoji} {p['nome']} • R$ {p['preco']:.2f}", value=f"{p.get('descricao', '')}\n{qtd_info}", inline=False)

    embed.set_footer(text="Selecione no menu ou botão abaixo para comprar instantaneamente!")
    return embed


class SalesCog(commands.Cog, name="Vendas"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            cid = interaction.data.get("custom_id", "")
            if cid.startswith("buy_item_"):
                try:
                    prod_id = int(cid.replace("buy_item_", ""))
                    produto = await db.get_produto_by_id(prod_id)
                    if not produto or not produto.get("ativo"):
                        return await interaction.response.send_message("❌ Este produto não está mais disponível na loja.", ephemeral=True)
                    await abrir_carrinho_usuario(interaction, produto)
                except Exception as e:
                    print(f"❌ Erro ao abrir carrinho pelo botão buy_item ({cid}): {e}")
                    if not interaction.response.is_done():
                        await interaction.response.send_message("❌ Ocorreu um erro ao abrir seu carrinho. Tente novamente.", ephemeral=True)
            elif cid.startswith("stock_item_"):
                try:
                    prod_id = int(cid.replace("stock_item_", ""))
                    produto = await db.get_produto_by_id(prod_id)
                    if not produto:
                        return await interaction.response.send_message("❌ Produto não encontrado.", ephemeral=True)
                    if produto["tipo"] in ("digital", "ambos"):
                        qtd = await db.get_estoque_count(prod_id)
                        txt = f"`{qtd} unidade(s)` disponível(is)" if qtd > 0 else "🔴 *Esgotado no momento*"
                    else:
                        txt = "🟢 *Ativação Automática Imediata (Cargo VIP)*"
                    await interaction.response.send_message(f"📦 Estoque atual de **{produto['nome']}**: {txt}", ephemeral=True)
                except Exception as e:
                    print(f"❌ Erro ao consultar estoque ({cid}): {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(SalesCog(bot))
