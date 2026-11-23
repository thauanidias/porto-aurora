import re
import ssl
from urllib.parse import urlparse
from uuid import UUID

from ldap3 import Connection, Server, Tls
from ldap3.core.exceptions import LDAPException, LDAPInvalidCredentialsResult
from ldap3.utils.conv import escape_filter_chars

from app.core.config import settings
from app.core.errors import DomainError


def authenticate(username: str, password: str, *, expected_email: str | None = None) -> bool:
    cfg = settings()
    if not cfg.ldap_enabled:
        raise DomainError("Autenticação corporativa não configurada.", 503)
    parsed = urlparse(cfg.ldap_url)
    if parsed.scheme != "ldaps" or not parsed.hostname or not password:
        raise DomainError("LDAP exige conexão LDAPS e parâmetros válidos.", 503)
    server = Server(
        parsed.hostname,
        port=parsed.port or 636,
        use_ssl=True,
        tls=Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=cfg.ldap_ca_cert_file or None),
        connect_timeout=10,
    )
    service = None
    try:
        service = Connection(
            server, user=cfg.ldap_bind_dn,
            password=cfg.ldap_bind_password.get_secret_value(),
            auto_bind=True, receive_timeout=10, raise_exceptions=True,
        )
        query = cfg.ldap_user_filter.replace(
            "{username}", escape_filter_chars(username.split("@")[0])
        )
        service.search(cfg.ldap_base_dn, query, attributes=["distinguishedName", "mail"], size_limit=2)
        if len(service.entries) != 1:
            return False
        if expected_email and str(service.entries[0].mail.value or "").strip().lower() != expected_email.lower():
            return False
        user_dn = service.entries[0].entry_dn
        try:
            with Connection(
                server, user=user_dn, password=password, auto_bind=True,
                receive_timeout=10, raise_exceptions=True,
            ) as user:
                return bool(user.bound)
        except LDAPInvalidCredentialsResult:
            return False
    except LDAPException as exc:
        raise DomainError("Não foi possível consultar o AD. Contate a TI.", 503) from exc
    finally:
        if service is not None:
            service.unbind()


def corporate_account(value: str) -> tuple[str, str]:
    """Normalize a network identifier without letting it choose another directory."""
    cfg = settings()
    value = value.strip().lower()
    if "\\" in value:
        domain, value = value.split("\\", 1)
        if not cfg.ldap_netbios_domain or domain != cfg.ldap_netbios_domain.lower():
            raise DomainError("Informe seu usuário de rede da empresa.", 401, "INVALID_CREDENTIALS")
    suffix = cfg.ldap_upn_suffix.strip().lower()
    if "@" in value:
        value, supplied_suffix = value.split("@", 1)
        if supplied_suffix != suffix:
            raise DomainError("Informe seu usuário de rede da empresa.", 401, "INVALID_CREDENTIALS")
    if not suffix or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", value):
        raise DomainError("Informe seu usuário de rede da empresa.", 401, "INVALID_CREDENTIALS")
    return value, value + "@" + suffix


def authenticate_directory(username: str, password: str) -> dict | None:
    """Bind as the supplied user and read their AD attributes. Never writes to AD."""
    cfg = settings()
    if not cfg.ldap_enabled:
        raise DomainError("Autenticação corporativa não configurada.", 503)
    parsed = urlparse(cfg.ldap_url)
    if parsed.scheme != "ldaps" or not parsed.hostname or not password or not cfg.ldap_base_dn:
        raise DomainError("A conexão segura com o AD não está configurada.", 503)
    account, principal = corporate_account(username)
    server = Server(parsed.hostname, port=parsed.port or 636, use_ssl=True, connect_timeout=10,
                    tls=Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=cfg.ldap_ca_cert_file or None,
                            valid_names=[parsed.hostname]))
    connection = None
    try:
        connection = Connection(server, user=principal, password=password, auto_bind=True,
                                receive_timeout=10, raise_exceptions=True)
        connection.search(cfg.ldap_base_dn,
            "(&(objectCategory=person)(objectClass=user)(sAMAccountName=" + escape_filter_chars(account) + "))",
            attributes=["objectGUID", "displayName", "mail", "department", "sAMAccountName", "userAccountControl"], size_limit=2)
        if len(connection.entries) != 1:
            return None
        entry = connection.entries[0]
        if int(entry.userAccountControl.value or 0) & 2:
            return None
        raw_guid = entry.objectGUID.value
        directory_id = str(UUID(bytes_le=raw_guid)) if isinstance(raw_guid, bytes) else str(UUID(str(raw_guid).strip("{}")))
        return {"directory_id": directory_id, "account": str(entry.sAMAccountName.value).lower(),
                "name": str(entry.displayName.value or "").strip(), "email": str(entry.mail.value or "").strip().lower(),
                "department": str(entry.department.value or "").strip()}
    except LDAPInvalidCredentialsResult:
        return None
    except (LDAPException, ValueError, OSError) as exc:
        raise DomainError("Não foi possível validar o acesso no AD. Tente novamente ou contate a TI.", 503) from exc
    finally:
        if connection is not None:
            connection.unbind()


def authenticate_saved_account(username: str, password: str, directory_id: str) -> bool:
    """Validate network credentials and the saved identity only; no profile import."""
    cfg = settings()
    if not cfg.ldap_enabled:
        raise DomainError("Autenticação corporativa não configurada.", 503)
    parsed = urlparse(cfg.ldap_url)
    if parsed.scheme != "ldaps" or not parsed.hostname or not password:
        raise DomainError("A conexão segura com o AD não está configurada.", 503)
    account, principal = corporate_account(username)
    guid_filter = "".join(f"\\{byte:02x}" for byte in UUID(directory_id).bytes_le)
    server = Server(parsed.hostname, port=parsed.port or 636, use_ssl=True, connect_timeout=10,
                    tls=Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=cfg.ldap_ca_cert_file or None,
                            valid_names=[parsed.hostname]))
    connection = None
    try:
        connection = Connection(server, user=principal, password=password, auto_bind=True,
                                receive_timeout=10, raise_exceptions=True)
        if not connection.bound:
            return False
        connection.search(cfg.ldap_base_dn,
            "(&(objectClass=user)(sAMAccountName=" + escape_filter_chars(account) + ")(objectGUID=" + guid_filter + "))",
            attributes=["objectGUID"], size_limit=1)
        return len(connection.entries) == 1
    except LDAPInvalidCredentialsResult:
        return False
    except (LDAPException, OSError) as exc:
        raise DomainError("Não foi possível validar sua senha de rede. Tente novamente ou contate a TI.", 503) from exc
    finally:
        if connection is not None:
            connection.unbind()
