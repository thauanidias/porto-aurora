from app.core.errors import DomainError


def require_corporate_manager_email(address: str) -> None:
    if address.strip().lower().rsplit("@", 1)[-1] != "portoaurora.example":
        raise DomainError("Use seu e-mail corporativo @portoaurora.example para solicitar acesso de gestor.")
