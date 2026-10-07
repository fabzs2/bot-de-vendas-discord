import io
import os
import uuid
import asyncio
import qrcode
from PIL import Image

try:
    import mercadopago
    MERCADOPAGO_AVAILABLE = True
except ImportError:
    MERCADOPAGO_AVAILABLE = False

class PaymentGateway:
    def __init__(self):
        self.default_access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "").strip()
        self.simulation_mode = os.getenv("SIMULATION_MODE", "false").lower() in ("true", "1", "yes")
        self._sdk_cache: dict[str, object] = {}

    def get_sdk(self, access_token: str = None):
        """Retorna a instância do SDK do Mercado Pago para um token específico (com cache)."""
        token = (access_token or self.default_access_token).strip()
        if not token or "SEU_TOKEN" in token or not MERCADOPAGO_AVAILABLE:
            return None

        if token in self._sdk_cache:
            return self._sdk_cache[token]

        try:
            sdk_instance = mercadopago.SDK(token)
            self._sdk_cache[token] = sdk_instance
            return sdk_instance
        except Exception as e:
            print(f"[Aviso] Falha ao instanciar SDK Mercado Pago com o token fornecido ({e}).")
            return None

    def is_simulation(self, access_token: str = None) -> bool:
        """Determina se as cobranças devem operar em modo simulação."""
        if self.simulation_mode:
            return True
        token = (access_token or self.default_access_token).strip()
        if not token or "SEU_TOKEN" in token or not MERCADOPAGO_AVAILABLE:
            return True
        return self.get_sdk(token) is None

    async def create_pix(self, amount: float, description: str, payer_name: str, order_id: str, access_token: str = None) -> dict:
        """Cria uma cobrança Pix via Mercado Pago (Multi-tenant) ou em Modo Simulação."""
        token = (access_token or self.default_access_token).strip()
        
        # Modo Simulação
        if self.is_simulation(token):
            fake_pix_id = f"SIM-{uuid.uuid4().hex[:12].upper()}"
            fake_copia_cola = f"00020126580014br.gov.bcb.pix0136botvendas-{fake_pix_id}5204000053039865405{amount:.2f}5802BR5920BOT VENDAS DISCORD6009SAO PAULO62070503***6304ABCD"
            return {
                "id": fake_pix_id,
                "status": "pending",
                "copia_cola": fake_copia_cola,
                "is_simulation": True
            }

        sdk = self.get_sdk(token)
        if not sdk:
            fake_pix_id = f"SIM-{uuid.uuid4().hex[:12].upper()}"
            return {
                "id": fake_pix_id,
                "status": "pending",
                "copia_cola": f"MODO-SIMULACAO-{fake_pix_id}",
                "is_simulation": True
            }

        # Mercado Pago Oficial
        def _request_mp():
            payment_data = {
                "transaction_amount": round(float(amount), 2),
                "description": f"{description[:50]} (Ped: {order_id})",
                "payment_method_id": "pix",
                "payer": {
                    "email": f"cliente_{order_id.lower()}@botvendas.com",
                    "first_name": payer_name[:30] if payer_name else "Cliente",
                }
            }
            return sdk.payment().create(payment_data)

        try:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, _request_mp)
            
            if res["status"] in (200, 201):
                resp_data = res["response"]
                point_of_interaction = resp_data.get("point_of_interaction", {})
                transaction_data = point_of_interaction.get("transaction_data", {})
                copia_cola = transaction_data.get("qr_code", "")
                
                return {
                    "id": str(resp_data["id"]),
                    "status": resp_data.get("status", "pending"),
                    "copia_cola": copia_cola,
                    "is_simulation": False
                }
            else:
                err_msg = res.get("response", {}).get("message", "Erro na API do Mercado Pago")
                print(f"[Erro Mercado Pago] {res['status']}: {err_msg}")
                fake_pix_id = f"FALLBACK-{uuid.uuid4().hex[:10]}"
                return {
                    "id": fake_pix_id,
                    "status": "pending",
                    "copia_cola": f"ERRO-MP: {err_msg}",
                    "is_simulation": True,
                    "error": err_msg
                }
        except Exception as e:
            print(f"[Erro Exceção Mercado Pago] {e}")
            fake_pix_id = f"ERR-{uuid.uuid4().hex[:10]}"
            return {
                "id": fake_pix_id,
                "status": "pending",
                "copia_cola": f"Erro de conexão com Mercado Pago: {e}",
                "is_simulation": True,
                "error": str(e)
            }

    async def check_status(self, payment_id: str, access_token: str = None) -> str:
        """Verifica o status do pagamento ('approved', 'pending', 'cancelled', etc.)."""
        if payment_id.startswith(("SIM-", "FALLBACK-", "ERR-")) or self.is_simulation(access_token):
            return "pending"

        sdk = self.get_sdk(access_token)
        if not sdk:
            return "pending"

        def _check_mp():
            return sdk.payment().get(int(payment_id))

        try:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, _check_mp)
            if res["status"] in (200, 201):
                return res["response"].get("status", "pending")
            return "pending"
        except Exception as e:
            print(f"[Erro verificação status PIX] {e}")
            return "pending"

def generate_qr_code_image(copia_cola: str) -> io.BytesIO:
    """Gera uma imagem PNG de alta resolução do QR Code Pix."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2
    )
    qr.add_data(copia_cola)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b0e14", back_color="#ffffff")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

gateway = PaymentGateway()
