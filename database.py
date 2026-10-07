import os
import aiosqlite
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendas.db")

async def _ensure_column(db, table: str, column: str, col_type: str):
    """Garante que uma coluna exista na tabela (migração de schema sem quebra)."""
    async with db.execute(f"PRAGMA table_info({table})") as cursor:
        cols = [r[1] for r in await cursor.fetchall()]
        if column not in cols:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

async def init_db(default_cargo_id: int = None):
    """Inicializa as tabelas do banco de dados SQLite com suporte a Multi-tenant (múltiplos servidores)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        
        # Tabela de Produtos (com suporte a guild_id)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                preco REAL NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'digital', -- 'digital', 'cargo', 'ambos'
                cargo_id INTEGER,
                emoji TEXT DEFAULT '📦',
                ativo INTEGER DEFAULT 1,
                guild_id INTEGER DEFAULT NULL
            );
        """)
        await _ensure_column(db, "produtos", "guild_id", "INTEGER DEFAULT NULL")

        # Tabela de Estoque para itens digitais
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                conteudo TEXT NOT NULL,
                adicionado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
            );
        """)

        # Tabela de Cupons
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cupons (
                codigo TEXT PRIMARY KEY,
                tipo TEXT NOT NULL DEFAULT 'percent', -- 'percent' ou 'fixo'
                valor REAL NOT NULL,
                usos_restantes INTEGER NOT NULL DEFAULT 100,
                ativo INTEGER DEFAULT 1,
                guild_id INTEGER DEFAULT NULL
            );
        """)
        await _ensure_column(db, "cupons", "guild_id", "INTEGER DEFAULT NULL")

        # Tabela de Pedidos
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_pedido TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                produto_id INTEGER NOT NULL,
                produto_nome TEXT NOT NULL,
                quantidade INTEGER NOT NULL DEFAULT 1,
                valor_unitario REAL NOT NULL,
                valor_total REAL NOT NULL,
                cupom_codigo TEXT,
                status TEXT NOT NULL DEFAULT 'pendente', -- 'pendente', 'aprovado', 'cancelado', 'expirado'
                pix_id TEXT,
                pix_copia_cola TEXT,
                entregue_conteudo TEXT,
                canal_id INTEGER,
                guild_id INTEGER DEFAULT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pago_em TIMESTAMP
            );
        """)
        await _ensure_column(db, "pedidos", "guild_id", "INTEGER DEFAULT NULL")

        # Tabela de Avaliações
        await db.execute("""
            CREATE TABLE IF NOT EXISTS avaliacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_codigo TEXT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                estrelas INTEGER NOT NULL,
                comentario TEXT,
                guild_id INTEGER DEFAULT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await _ensure_column(db, "avaliacoes", "guild_id", "INTEGER DEFAULT NULL")

        # Tabela de Configurações (chave-valor por servidor)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT NOT NULL,
                guild_id INTEGER NOT NULL DEFAULT 0,
                valor TEXT NOT NULL,
                PRIMARY KEY (chave, guild_id)
            );
        """)
        # Verifica se a tabela legada precisa de coluna guild_id
        await _ensure_column(db, "configuracoes", "guild_id", "INTEGER NOT NULL DEFAULT 0")

        # Se não houver produtos cadastrados, cria o produto padrão VIP
        async with db.execute("SELECT COUNT(*) FROM produtos") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                await db.execute("""
                    INSERT INTO produtos (nome, descricao, preco, tipo, cargo_id, emoji, ativo, guild_id)
                    VALUES (?, ?, ?, ?, ?, ?, 1, NULL)
                """, ("Plano VIP", "Acesso aos canais exclusivos e benefícios especiais", 15.00, "cargo", default_cargo_id, "⭐"))
                
                # Cria cupom de boas-vindas padrão de 10%
                await db.execute("""
                    INSERT OR IGNORE INTO cupons (codigo, tipo, valor, usos_restantes, ativo, guild_id)
                    VALUES ('BEMVINDO', 'percent', 10.0, 50, 1, NULL)
                """)

        await db.commit()

# ==============================================================================
# PRODUTOS (COM SUPORTE MULTI-TENANT)
# ==============================================================================
async def get_produtos(guild_id: int = None, apenas_ativos: bool = True):
    """Retorna produtos cadastrados. Se guild_id for fornecido, filtra pelos produtos do servidor ou globais."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        conditions = []
        params = []
        
        if apenas_ativos:
            conditions.append("ativo = 1")
            
        if guild_id is not None:
            conditions.append("(guild_id = ? OR guild_id IS NULL)")
            params.append(guild_id)
            
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM produtos {where_clause} ORDER BY id ASC"
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_produto_by_id(produto_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def add_produto(nome: str, descricao: str, preco: float, tipo: str, cargo_id: int = None, emoji: str = "📦", guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO produtos (nome, descricao, preco, tipo, cargo_id, emoji, ativo, guild_id)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (nome, descricao, preco, tipo, cargo_id, emoji, guild_id))
        await db.commit()
        return cursor.lastrowid

async def update_produto(produto_id: int, nome: str, descricao: str, preco: float, tipo: str, cargo_id: int = None, emoji: str = "📦"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE produtos 
            SET nome = ?, descricao = ?, preco = ?, tipo = ?, cargo_id = ?, emoji = ?
            WHERE id = ?
        """, (nome, descricao, preco, tipo, cargo_id, emoji, produto_id))
        await db.commit()

async def delete_produto(produto_id: int, guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if guild_id is not None:
            await db.execute("DELETE FROM produtos WHERE id = ? AND (guild_id = ? OR guild_id IS NULL)", (produto_id, guild_id))
        else:
            await db.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
        await db.execute("DELETE FROM estoque WHERE produto_id = ?", (produto_id,))
        await db.commit()

# ==============================================================================
# ESTOQUE
# ==============================================================================
async def add_estoque_itens(produto_id: int, itens: list[str]):
    """Adiciona uma lista de linhas/itens ao estoque de um produto."""
    async with aiosqlite.connect(DB_PATH) as db:
        data = [(produto_id, item.strip()) for item in itens if item.strip()]
        await db.executemany("INSERT INTO estoque (produto_id, conteudo) VALUES (?, ?)", data)
        await db.commit()
        return len(data)

async def get_estoque_count(produto_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM estoque WHERE produto_id = ?", (produto_id,)) as cursor:
            return (await cursor.fetchone())[0]

async def consumir_estoque(produto_id: int, quantidade: int = 1) -> list[str]:
    """Retira atomicamente X itens do estoque e retorna seus conteúdos."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT id, conteudo FROM estoque WHERE produto_id = ? ORDER BY id ASC LIMIT ?
        """, (produto_id, quantidade)) as cursor:
            rows = await cursor.fetchall()
            
        if len(rows) < quantidade:
            return []
            
        ids = [r["id"] for r in rows]
        conteudos = [r["conteudo"] for r in rows]
        
        placeholders = ",".join("?" for _ in ids)
        await db.execute(f"DELETE FROM estoque WHERE id IN ({placeholders})", ids)
        await db.commit()
        return conteudos

async def devolver_estoque(produto_id: int, itens: list[str]):
    """Devolve itens ao estoque caso um pedido seja cancelado."""
    return await add_estoque_itens(produto_id, itens)

async def limpar_estoque(produto_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM estoque WHERE produto_id = ?", (produto_id,))
        await db.commit()

# ==============================================================================
# CUPONS
# ==============================================================================
async def get_cupom(codigo: str, guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM cupons WHERE codigo = ? AND ativo = 1 AND usos_restantes > 0"
        params = [codigo.upper().strip()]
        if guild_id is not None:
            query += " AND (guild_id = ? OR guild_id IS NULL)"
            params.append(guild_id)

        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def add_cupom(codigo: str, tipo: str, valor: float, usos: int = 100, guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO cupons (codigo, tipo, valor, usos_restantes, ativo, guild_id)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (codigo.upper().strip(), tipo, valor, usos, guild_id))
        await db.commit()

async def get_all_cupons(guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM cupons"
        params = []
        if guild_id is not None:
            query += " WHERE (guild_id = ? OR guild_id IS NULL)"
            params.append(guild_id)
        query += " ORDER BY ativo DESC, codigo ASC"
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def delete_cupom(codigo: str, guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query = "DELETE FROM cupons WHERE codigo = ?"
        params = [codigo.upper().strip()]
        if guild_id is not None:
            query += " AND (guild_id = ? OR guild_id IS NULL)"
            params.append(guild_id)
        await db.execute(query, params)
        await db.commit()

async def decrementar_cupom(codigo: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE cupons 
            SET usos_restantes = usos_restantes - 1,
                ativo = CASE WHEN usos_restantes - 1 <= 0 THEN 0 ELSE ativo END
            WHERE codigo = ?
        """, (codigo.upper().strip(),))
        await db.commit()

# ==============================================================================
# PEDIDOS
# ==============================================================================
async def criar_pedido(codigo_pedido: str, user_id: int, user_name: str, produto_id: int, produto_nome: str,
                       quantidade: int, valor_unitario: float, valor_total: float, cupom_codigo: str = None,
                       pix_id: str = None, pix_copia_cola: str = None, canal_id: int = None, guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO pedidos (
                codigo_pedido, user_id, user_name, produto_id, produto_nome,
                quantidade, valor_unitario, valor_total, cupom_codigo,
                status, pix_id, pix_copia_cola, canal_id, guild_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?, ?, ?)
        """, (codigo_pedido, user_id, user_name, produto_id, produto_nome,
              quantidade, valor_unitario, valor_total, cupom_codigo,
              pix_id, pix_copia_cola, canal_id, guild_id))
        await db.commit()

async def get_pedido(codigo_pedido: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM pedidos WHERE codigo_pedido = ?", (codigo_pedido,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_pedido_pendente_usuario(user_id: int, guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM pedidos WHERE user_id = ? AND status = 'pendente'"
        params = [user_id]
        if guild_id is not None:
            query += " AND (guild_id = ? OR guild_id IS NULL)"
            params.append(guild_id)
        query += " ORDER BY id DESC LIMIT 1"
        
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def marcar_pedido_pago(codigo_pedido: str, entregue_conteudo: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("""
            UPDATE pedidos
            SET status = 'aprovado', pago_em = ?, entregue_conteudo = ?
            WHERE codigo_pedido = ?
        """, (now, entregue_conteudo, codigo_pedido))
        await db.commit()

async def marcar_pedido_cancelado(codigo_pedido: str, status: str = 'cancelado'):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE pedidos SET status = ? WHERE codigo_pedido = ?
        """, (status, codigo_pedido))
        await db.commit()

# ==============================================================================
# AVALIAÇÕES
# ==============================================================================
async def add_avaliacao(pedido_codigo: str, user_id: int, user_name: str, estrelas: int, comentario: str, guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO avaliacoes (pedido_codigo, user_id, user_name, estrelas, comentario, guild_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pedido_codigo, user_id, user_name, estrelas, comentario, guild_id))
        await db.commit()

# ==============================================================================
# CONFIGURAÇÕES GERAIS (MULTI-TENANT POR GUILD_ID)
# ==============================================================================
async def set_config(chave: str, valor: str, guild_id: int = 0):
    """Salva uma configuração para um servidor específico (ou 0 para global)."""
    gid = int(guild_id) if guild_id else 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM configuracoes WHERE chave = ? AND guild_id = ?", (chave, gid))
        await db.execute("""
            INSERT INTO configuracoes (chave, guild_id, valor) VALUES (?, ?, ?)
        """, (chave, gid, str(valor)))
        await db.commit()

async def get_config(chave: str, default=None, guild_id: int = 0):
    """Busca uma configuração do servidor específico. Se não achar, faz fallback para o global (0) ou default."""
    gid = int(guild_id) if guild_id else 0
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Tenta buscar específico da guild
        if gid != 0:
            async with db.execute("SELECT valor FROM configuracoes WHERE chave = ? AND guild_id = ?", (chave, gid)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]

        # 2. Fallback para global (guild_id = 0)
        async with db.execute("SELECT valor FROM configuracoes WHERE chave = ? AND guild_id = 0", (chave,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]

        return default

async def set_guild_mercadopago_token(guild_id: int, token: str):
    """Configura o token do Mercado Pago específico para este servidor."""
    await set_config("mercadopago_token", token.strip(), guild_id=guild_id)

async def remove_guild_mercadopago_token(guild_id: int):
    """Remove o token customizado do Mercado Pago deste servidor."""
    gid = int(guild_id) if guild_id else 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM configuracoes WHERE chave = 'mercadopago_token' AND guild_id = ?", (gid,))
        await db.commit()

async def get_guild_mercadopago_token(guild_id: int = 0) -> str:
    """Retorna o token do Mercado Pago da guild ou o padrão do .env."""
    token = await get_config("mercadopago_token", default=None, guild_id=guild_id)
    if token:
        return token
    return os.getenv("MERCADOPAGO_ACCESS_TOKEN", "").strip()

# ==============================================================================
# ESTATÍSTICAS E DASHBOARD
# ==============================================================================
async def get_estatisticas(guild_id: int = None):
    """Gera o balanço financeiro e métricas de vendas, filtrando por servidor se especificado."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        guild_filter = "AND (guild_id = ? OR guild_id IS NULL)" if guild_id is not None else ""
        params = [guild_id] if guild_id is not None else []
        
        # Total aprovado geral
        q_geral = f"SELECT COUNT(*) as total_vendas, COALESCE(SUM(valor_total), 0) as faturamento_total FROM pedidos WHERE status = 'aprovado' {guild_filter}"
        async with db.execute(q_geral, params) as cursor:
            geral = dict(await cursor.fetchone())
            
        # Vendas hoje
        q_hoje = f"""
            SELECT COUNT(*) as vendas_hoje, COALESCE(SUM(valor_total), 0) as faturamento_hoje 
            FROM pedidos 
            WHERE status = 'aprovado' AND DATE(pago_em) = DATE('now', 'localtime') {guild_filter}
        """
        async with db.execute(q_hoje, params) as cursor:
            hoje = dict(await cursor.fetchone())

        # Top 5 produtos
        q_top = f"""
            SELECT produto_nome, COUNT(*) as qtd_vendas, SUM(valor_total) as receita
            FROM pedidos
            WHERE status = 'aprovado' {guild_filter}
            GROUP BY produto_nome
            ORDER BY qtd_vendas DESC
            LIMIT 5
        """
        async with db.execute(q_top, params) as cursor:
            top_produtos = [dict(r) for r in await cursor.fetchall()]

        return {
            "total_vendas": geral["total_vendas"],
            "faturamento_total": geral["faturamento_total"],
            "vendas_hoje": hoje["vendas_hoje"],
            "faturamento_hoje": hoje["faturamento_hoje"],
            "top_produtos": top_produtos
        }
