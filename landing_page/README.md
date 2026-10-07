# 🌐 Landing Page de Vendas (Integrada com a Kiwify)

Uma página de vendas moderna, responsiva e com estética **Discord Dark Premium**, pronta para direcionar compradores para o seu checkout da **Kiwify**.

---

## ⚡ Como Personalizar o Link de Compra da Kiwify

1. Abra o arquivo `script.js`.
2. Na primeira linha, substitua o link de exemplo pelo seu link de checkout real da Kiwify:
   ```javascript
   const KIWIFY_CHECKOUT_URL = "https://pay.kiwify.com.br/SEU_LINK_AQUI";
   ```
3. Pronto! Todos os botões "Comprar Agora" da página serão atualizados automaticamente.

---

## 🖥️ Como Visualizar no seu Computador

Você pode simplesmente **dar dois cliques no arquivo `index.html`** para abrir no seu navegador, ou rodar um servidor local:

```bash
cd landing_page
python3 -m http.server 8080
```
Depois acesse `http://localhost:8080` no navegador.

---

## 🚀 Como Hospedar 100% Grátis em 2 Minutos

### Opção 1: Vercel (Recomendada - Mais Fácil)
1. Crie uma conta gratuita em [vercel.com](https://vercel.com).
2. Arraste a pasta `landing_page` para o painel da Vercel.
3. Sua página estará online imediatamente com certificado SSL gratuito (`https://suapagina.vercel.app`).
4. Cole essa URL no campo **Página de Vendas** dentro da Kiwify!

### Opção 2: Netlify Drop
1. Acesse [app.netlify.com/drop](https://app.netlify.com/drop).
2. Arraste e solte a pasta `landing_page`.
3. Pronto! Seu site estará publicado em 10 segundos.

### Opção 3: GitHub Pages
1. Crie um repositório no GitHub.
2. Suba os arquivos da pasta `landing_page`.
3. Vá em **Settings > Pages** e ative o GitHub Pages.
