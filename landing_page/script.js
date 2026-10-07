/**
 * CONFIGURAÇÃO DA PÁGINA DE VENDAS
 * ==============================================================================
 * Basta alterar a constante abaixo com o seu link de checkout gerado na Kiwify!
 * Exemplo: const KIWIFY_CHECKOUT_URL = "https://pay.kiwify.com.br/abc1234";
 * ==============================================================================
 */
const KIWIFY_CHECKOUT_URL = "https://pay.kiwify.com.br/SEU_CODIGO_AQUI";

document.addEventListener("DOMContentLoaded", () => {
  // 1. Atualiza todos os botões e links com a URL da Kiwify
  const kiwifyLinks = document.querySelectorAll(".kiwify-link");
  kiwifyLinks.forEach(link => {
    if (KIWIFY_CHECKOUT_URL && KIWIFY_CHECKOUT_URL !== "https://pay.kiwify.com.br/SEU_CODIGO_AQUI") {
      link.href = KIWIFY_CHECKOUT_URL;
    }
  });

  // 2. Interatividade do FAQ (Acordeão)
  const faqItems = document.querySelectorAll(".faq-item");
  faqItems.forEach(item => {
    const question = item.querySelector(".faq-question");
    question.addEventListener("click", () => {
      const isActive = item.classList.contains("active");

      // Fecha todos os outros itens
      faqItems.forEach(otherItem => {
        otherItem.classList.remove("active");
      });

      // Se não estava ativo, abre
      if (!isActive) {
        item.classList.add("active");
      }
    });
  });

  // 3. Botão de Copiar Código Pix Simulado no Mockup
  const btnCopy = document.querySelector(".btn-copy-code");
  if (btnCopy) {
    btnCopy.addEventListener("click", () => {
      const originalText = btnCopy.textContent;
      btnCopy.textContent = "Copiado!";
      btnCopy.style.background = "#10B981";
      setTimeout(() => {
        btnCopy.textContent = originalText;
        btnCopy.style.background = "#5865F2";
      }, 2000);
    });
  }

  // Abre o primeiro item do FAQ por padrão
  if (faqItems.length > 0) {
    faqItems[0].classList.add("active");
  }
});
