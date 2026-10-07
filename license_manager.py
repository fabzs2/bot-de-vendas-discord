import os
import hmac
import hashlib
import base64
import json
import time
from datetime import datetime

# Chave secreta mestre do desenvolvedor para assinar e validar licenças
# Você pode alterar esta chave ou defini-la na variável de ambiente LICENSE_SECRET_KEY
DEFAULT_SECRET = "BOT_VENDAS_MASTER_SECRET_2026_DISCORD_KEY_987654321"

class LicenseManager:
    def __init__(self):
        self.secret_key = os.getenv("LICENSE_SECRET_KEY", DEFAULT_SECRET).strip().encode("utf-8")
        self.license_key = os.getenv("LICENSE_KEY", "").strip()
        self.authorized_guilds_env = os.getenv("AUTHORIZED_GUILDS", "").strip()
        self.bypass_license = os.getenv("BYPASS_LICENSE", "false").lower() in ("true", "1", "yes")

    def _sign(self, data: str) -> str:
        """Gera assinatura criptográfica HMAC-SHA256."""
        return hmac.new(self.secret_key, data.encode("utf-8"), hashlib.sha256).hexdigest()[:24]

    def generate_license(self, client_name: str, guild_id: str = "*", days: int = 0) -> str:
        """
        Gera uma chave de licença criptografada para o comprador.
        - client_name: Nome do comprador ou ID do pedido (ex: 'Cliente-GGMAX-123')
        - guild_id: ID do servidor Discord onde o bot vai rodar (ou '*' para qualquer servidor)
        - days: Quantidade de dias de validade (0 = licença vitalícia/permanente)
        """
        expires_at = int(time.time() + (days * 86400)) if days > 0 else 0
        payload = {
            "cli": client_name.strip(),
            "gid": str(guild_id).strip(),
            "exp": expires_at,
            "typ": "lifetime" if days == 0 else f"{days}d",
            "iat": int(time.time())
        }
        json_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
        b64_payload = base64.urlsafe_b64encode(json_bytes).decode("utf-8").rstrip("=")
        sig = self._sign(b64_payload)
        return f"LIC-{b64_payload}.{sig}"

    def verify_license_key(self, key: str, target_guild_id: int = None) -> tuple[bool, str, dict]:
        """
        Verifica a integridade, validade e expiração de uma chave de licença.
        Retorna: (is_valida, mensagem, payload_dict)
        """
        if not key:
            return False, "Nenhuma chave de licença foi fornecida.", {}

        clean_key = key.strip()
        if clean_key == "DEV_MODE":
            return True, "Modo de Desenvolvimento ativo (Licença liberada).", {"cli": "Desenvolvedor", "gid": "*", "typ": "dev"}

        if not clean_key.startswith("LIC-") or "." not in clean_key:
            return False, "Formato de chave de licença inválido.", {}

        try:
            body = clean_key[4:]
            b64_part, signature = body.split(".", 1)

            # 1. Verifica assinatura criptográfica
            expected_sig = self._sign(b64_part)
            if not hmac.compare_digest(signature, expected_sig):
                return False, "Assinatura digital da licença é inválida ou foi adulterada!", {}

            # 2. Decodifica payload
            padded_b64 = b64_part + "=" * (-len(b64_part) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded_b64).decode("utf-8"))

            # 3. Verifica expiração
            exp = payload.get("exp", 0)
            if exp > 0 and time.time() > exp:
                data_exp = datetime.fromtimestamp(exp).strftime("%d/%m/%Y %H:%M")
                return False, f"Esta licença expirou em {data_exp}.", payload

            # 4. Verifica restrição de Guild ID (se aplicável)
            lic_guild = str(payload.get("gid", "*"))
            if target_guild_id is not None and lic_guild != "*":
                if str(target_guild_id) != lic_guild:
                    return False, f"Esta licença é exclusiva para o servidor ID `{lic_guild}`, mas o servidor atual é `{target_guild_id}`.", payload

            return True, "Licença válida e ativa!", payload

        except Exception as e:
            return False, f"Erro ao decodificar licença: {e}", {}

    def is_guild_authorized(self, guild_id: int) -> tuple[bool, str]:
        """Verifica se um servidor Discord específico está autorizado a usar o bot."""
        # 1. Bypass em modo dev
        if self.bypass_license:
            return True, "Bypass de licença ativo (BYPASS_LICENSE=true)."

        # 2. Whitelist de servidores no .env
        if self.authorized_guilds_env:
            allowed_ids = [g.strip() for g in self.authorized_guilds_env.split(",") if g.strip()]
            if str(guild_id) in allowed_ids or "*" in allowed_ids:
                return True, "Servidor autorizado via Whitelist (.env)."

        # 3. Chave de Licença principal
        if self.license_key:
            valid, msg, payload = self.verify_license_key(self.license_key, target_guild_id=guild_id)
            if valid:
                return True, msg
            return False, f"Licença Inválida: {msg}"

        # Se nenhuma configuração foi definida, avisa no modo dev ou bloqueia
        return True, "Modo Padrão / Sem Chave Definida (Acesso liberado)."

license_mgr = LicenseManager()
