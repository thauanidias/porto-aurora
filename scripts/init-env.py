"""Create local secrets once; never print secret values."""

import base64
import secrets
from pathlib import Path

target = Path(".env")
if target.exists():
    raise SystemExit(".env já existe; nenhuma alteração realizada")
text = Path(".env.example").read_text(encoding="utf-8")
text = text.replace("CHANGE_DATABASE_PASSWORD", secrets.token_hex(24))
text = text.replace("CHANGE_JWT_SECRET", secrets.token_hex(48))
text = text.replace(
    "CHANGE_ENCRYPTION_KEY", base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
)
target.write_text(text, encoding="utf-8")
print(
    ".env criado com segredos aleatórios. Revise URL e integrações antes de produção."
)
