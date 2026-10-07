# 🛒 Bot de Vendas Discord Definitivo (Vendas Automáticas com Pix)

Um sistema completo, profissional e automatizado de vendas para o Discord com suporte a **Pix Automático (Mercado Pago)**, geração instantânea de **QR Code em alta definição**, código **Pix Copia e Cola**, entrega atômica de **Cargos VIP** e **Itens Digitais (Chaves, Contas e Links)**, sistema de **Cupons de Desconto**, **Carrinho Privado (Tickets)**, **Avaliações com Estrelas**, **Dashboard Financeiro**, **Arquitetura Multi-Tenant** e **Sistema de Licenciamento Anti-Pirataria**.

---

## 🌟 Principais Recursos

- ⚡ **Pix 100% Automático:**
  - Geração nativa de imagem do QR Code Pix renderizada e enviada no Discord.
  - Caixa com código Pix Copia e Cola para copiar em um clique no celular.
  - Verificação assíncrona periódica de pagamento a cada poucos segundos.
  - **Modo Simulação / Dev:** Permite testar todo o fluxo de compra e entrega sem precisar gastar dinheiro real!

- 🏢 **Arquitetura Multi-Tenant (Multi-Servidor):**
  - O mesmo bot pode atender diversos servidores com **isolamento completo**.
  - Cada servidor pode configurar seu próprio token Pix do Mercado Pago (`/configurar mercadopago definir`), garantindo que o dinheiro caia na conta bancária de cada dono de servidor separadamente.
  - Produtos, estoques, cupons, logs e estatísticas são isolados por servidor.

- 🔑 **Sistema de Licenças e Proteção Anti-Pirataria:**
  - Validador criptográfico HMAC-SHA256 para controle de clientes.
  - Ferramenta inclusa (`license_tool.py`) para gerar licenças mensais ou vitalícias vinculadas ao servidor do comprador.
  - Script automático (`build_dist.py`) para gerar pacotes `.zip` 100% limpos e prontos para venda no GGMAX, DFG ou Mercado Livre.

- 📦 **Catálogo & Gestão de Estoque:**
  - Suporte a produtos de **Cargo VIP** (adiciona o cargo automaticamente).
  - Suporte a produtos de **Estoque Digital** (chaves, contas, licenças com consumo atômico por linha).
  - Suporte a produtos **Mistos** (entrega cargo no servidor + chave por DM ao mesmo tempo).
  - Se o estoque esgotar, o bot impede a venda e exibe o status de esgotado.

- 🛒 **Carrinho de Compras Interativo:**
  - Criação de canais privados temporários para cada comprador.
  - Proteção anti-duplicação (redireciona para carrinho já aberto).
  - Seleção dinâmica de quantidade (`+1` / `-1`).
  - Botão de cancelamento e expiração automática após 15 minutos de inatividade.

- 🎟️ **Sistema de Cupons de Desconto:**
  - Crie cupons por porcentagem (`10% OFF`) ou valor fixo (`R$ 5,00 OFF`).
  - Limite de usos por cupom.
  - Aplicação interativa via Modal no carrinho.

- 📥 **Entrega Imediata e Segura:**
  - Envio do produto formatado na DM do comprador com recibo numerado (`#PED-XXXXXX`).
  - Fallback automático: caso a DM do cliente esteja fechada, entrega no próprio canal do carrinho antes de fechá-lo.

- ⭐ **Sistema de Prova Social (Avaliações):**
  - Após a entrega, o cliente pode clicar no botão `Avaliar Atendimento`.
  - Formulário com nota de 1 a 5 estrelas e comentário.
  - Envio automático no canal público de `#avaliações` com avatar e estrelas douradas!

- 📊 **Dashboard Financeiro & Auditoria:**
  - Comando `/estatisticas` com total arrecadado hoje, faturamento geral e Top 5 produtos mais vendidos por servidor.
  - Canal de Logs de Vendas com registro detalhado de cada transação.

---

## 📋 Lista de Comandos Slash (/)

| Comando | Descrição | Permissão |
|---|---|---|
| `/painel` (ou `/gerenciar`) | **Central Interativa de Gerenciamento** (Menu de criação, estoque, cupons, Pix e publicação de vitrine) | Administrador |
| `/enviarpainel` (ou `/vitrine`) | Envia a vitrine no canal com opção de escolher **Item Individual** ou **Grupo** (Digital / Cargo VIP / Todos) | Administrador |
| `/estatisticas` | Exibe métricas de vendas, faturamento diário e produtos top | Administrador |
| `/configurar canais` | Define o canal de logs, canal de avaliações e categoria de carrinhos | Administrador |
| `/configurar mercadopago definir` | Define o Access Token Pix exclusivo deste servidor | Administrador |
| `/configurar mercadopago remover` | Remove o token personalizado e volta ao padrão | Administrador |
| `/configurar gateway` | Mostra o status do gateway de pagamento ativo no servidor | Administrador |

> **Comandos com Prefixo (!):**
> - `!sync`: Força a sincronização imediata de todos os comandos Slash no servidor.
> - `!enviarpainel`: Envia a vitrine no canal atual.

> **💡 Publicação Flexível:**
> - Você pode postar um **Item Individual** (card exclusivo com botão de compra direta e consulta de estoque).
> - Ou postar por **Grupo** (Apenas Digitais, Apenas Cargos VIP ou Todos os Produtos).
> - Disponível tanto no botão **📢 Publicar Vitrine** do `/painel` quanto via parâmetros nos comandos `/enviarpainel` e `/vitrine`!

---

## 🚀 Como Iniciar o Bot

### Opção 1: Inicializador Automático (1 Clique)
- **Windows:** Dê dois cliques em `iniciar.bat`. O script cria o ambiente virtual, instala as dependências e inicia o bot.
- **Linux / macOS:** Execute `./iniciar.sh`.

### Opção 2: Manualmente via Terminal
```bash
# 1. Crie o ambiente virtual
python3 -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Inicie o bot
python3 main.py
```

### Opção 3: Docker / Docker Compose
```bash
docker compose up -d
```

### Opção 4: Hospedagens Populares (Discloud / Square Cloud)
- **Discloud:** O arquivo `discloud.config` já está incluído. Basta compactar a pasta e fazer upload.
- **Square Cloud:** O arquivo `squarecloud.app` já está configurado.

---

## 🔑 Como Gerar Licenças para Seus Clientes

Para criar chaves de acesso para os compradores do seu bot:

```bash
# Licença de 30 dias para um servidor específico:
python3 license_tool.py generate --client "Cliente-GGMAX" --guild 123456789012345678 --days 30

# Licença vitalícia (sem expiração):
python3 license_tool.py generate --client "Cliente-VIP" --guild 123456789012345678 --lifetime

# Inspecionar uma chave existente:
python3 license_tool.py inspect --key "LIC-..."
```

O comprador só precisa colocar a chave gerada no arquivo `.env` dele:
```env
LICENSE_KEY=LIC-sua_chave_aqui
```

---

## 📦 Como Empacotar para Venda (Gerar ZIP Limpo)

Antes de entregar o bot para um cliente que comprou no GGMAX, DFG ou Mercado Livre:

```bash
python3 build_dist.py
```
O script gera um arquivo ZIP dentro da pasta `dist/` limpo de dados sensíveis (sem seu `.env` privado e sem seu banco `vendas.db`).

---

## ⚙️ Configuração do Arquivo `.env`

Copie o `.env.example` para `.env`:

```env
# Token do bot criado no Discord Developer Portal
DISCORD_TOKEN=seu_token_aqui

# ID do cargo VIP padrão
CARGO_VIP=1234567890123456789

# Token Padrão do Mercado Pago (ou cada servidor configura o seu via /configurar mercadopago)
MERCADOPAGO_ACCESS_TOKEN=APP_USR-xxxxxxxxxxxxxxxxxxxxxxxxxx

# Modo de Simulação ('true' para testes sem dinheiro, 'false' para Mercado Pago Real)
SIMULATION_MODE=false

# Chave de licença (use DEV_MODE para testes locais)
LICENSE_KEY=DEV_MODE
```

---

## 🔒 Permissões do Discord

- **Hierarquia de Cargos:** No Discord, posicione o cargo do Bot **acima** dos cargos que ele entrega (como o VIP).
- **Intents Habilitadas:** No Discord Developer Portal, ative as 3 opções em **Privileged Gateway Intents**:
  - `PRESENCE INTENT`
  - `SERVER MEMBERS INTENT`
  - `MESSAGE CONTENT INTENT`
