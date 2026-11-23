from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: str
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: SecretStr
    encryption_key: SecretStr
    public_url: str = "http://localhost:8088"
    rh_url: str = ""
    manager_url: str = ""
    cors_origins: str = "http://localhost:8088,http://localhost:5173"
    trusted_proxy_hosts: str = "nginx"
    access_minutes: int = 15
    refresh_days: int = 7
    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 10
    resume_ai_url: str = "http://resume-ai:11434"
    resume_ai_model: str = "qwen2.5:3b"
    resume_ai_enabled: bool = False
    clamav_enabled: bool = True
    clamav_host: str = "clamav"
    smtp_enabled: bool = False
    test_email_enabled: bool = False
    email_verification_required: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    smtp_starttls: bool = True
    smtp_auth_mode: Literal["basic", "oauth2"] = "basic"
    smtp_oauth_tenant_id: str = ""
    smtp_oauth_client_id: str = ""
    smtp_oauth_client_secret: SecretStr = SecretStr("")
    ldap_enabled: bool = False
    ldap_url: str = ""
    ldap_base_dn: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: SecretStr = SecretStr("")
    ldap_user_filter: str = "(sAMAccountName={username})"
    ldap_group_base: str = ""
    ldap_ca_cert_file: str = ""
    ldap_upn_suffix: str = ""
    ldap_netbios_domain: str = ""
    ldap_rh_only: bool = False
    ldap_rh_access_mode: Literal["directory", "saved"] = "saved"
    ldap_rh_store_password: bool = False
    ldap_rh_departments: str = "RH"
    ldap_rh_exception_ids: str = ""
    ldap_rh_session_minutes: int = Field(default=30, ge=5, le=480)
    ldap_rh_role: Literal["RECRUTADOR", "ANALISTA_RH", "RH_ADMIN"] = "RECRUTADOR"
    graph_enabled: bool = False
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: SecretStr = SecretStr("")
    graph_user_id: str = ""
    webhook_allowed_hosts: str = ""

    @model_validator(mode="after")
    def secure_configuration(self):
        if self.ldap_rh_only and (not self.ldap_enabled or not self.ldap_base_dn or not self.ldap_upn_suffix
                                 or not self.ldap_rh_departments.strip() or not self.ldap_url.startswith("ldaps://")):
            raise ValueError("O acesso RH pelo AD exige LDAPS, base, domínio e departamento configurados")
        if len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET deve conter pelo menos 32 caracteres aleatórios")
        if self.rh_url or self.manager_url:
            urls = [urlsplit(value) for value in (self.public_url, self.rh_url, self.manager_url)]
            if any(not url.hostname or url.scheme not in {"http", "https"}
                   or url.username or url.password or url.path not in {"", "/"}
                   or url.query or url.fragment for url in urls):
                raise ValueError("Configure os três portais com URLs de origem válidas")
            if len({url.hostname for url in urls}) != 3:
                raise ValueError("Os três portais devem usar hosts distintos")
            if self.environment == "production" and any(url.scheme != "https" for url in urls):
                raise ValueError("Os três portais de produção exigem HTTPS")
        if self.environment == "production":
            if self.test_email_enabled:
                raise ValueError("E-mail de teste não pode ser usado em produção")
            if not self.public_url.startswith("https://") or not self.clamav_enabled:
                raise ValueError("Produção exige HTTPS e validação antimalware")
        if self.smtp_enabled and self.smtp_auth_mode == "oauth2":
            if not all(
                (
                    self.smtp_host,
                    self.smtp_from,
                    self.smtp_oauth_tenant_id,
                    self.smtp_oauth_client_id,
                    self.smtp_oauth_client_secret.get_secret_value(),
                    self.smtp_starttls,
                )
            ):
                raise ValueError("SMTP OAuth2 exige servidor, remetente, Entra ID e STARTTLS")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
