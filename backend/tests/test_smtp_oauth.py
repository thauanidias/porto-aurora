from types import SimpleNamespace

from app.integrations import delivery


def test_microsoft_365_smtp_uses_oauth2_and_starttls(monkeypatch):
    config = SimpleNamespace(
        enabled=True,
        sender="talentos@example.com",
        host="smtp.office365.com",
        port=587,
        starttls=True,
        auth_mode="oauth2",
        tenant_id="tenant-id",
        client_id="client-id",
        client_secret="client-secret",
    )
    monkeypatch.setattr(delivery, "smtp_runtime", lambda _: config)
    observed = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "access-token"}

    def fake_post(url, *, data, timeout):
        observed["token_url"] = url
        observed["token_data"] = data
        observed["timeout"] = timeout
        return FakeResponse()

    class FakeSMTP:
        def __init__(self, host, port, *, timeout):
            observed["server"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def starttls(self, *, context):
            observed["tls"] = context is not None

        def ehlo(self):
            observed["ehlo"] = True

        def auth(self, mechanism, response):
            observed["auth"] = (mechanism, response(None))

        def send_message(self, message):
            observed["from"] = message["From"]
            observed["to"] = message["To"]
            observed["body"] = message.get_body(preferencelist=("plain",)).get_content()
            observed["html"] = message.get_body(preferencelist=("html",)).get_content()
            observed["logo"] = any(part.get("Content-ID") == "<tgpm-logo>" for part in message.walk())

    monkeypatch.setattr(delivery.httpx, "post", fake_post)
    monkeypatch.setattr(delivery.smtplib, "SMTP", FakeSMTP)
    delivery.send_email(
        {"recipient": "candidate@example.com", "subject": "Confirme o e-mail", "body": "Link"},
        "message-key",
    )

    assert observed["server"] == ("smtp.office365.com", 587, 20)
    assert observed["tls"] and observed["ehlo"]
    assert observed["token_url"].endswith("/tenant-id/oauth2/v2.0/token")
    assert observed["token_data"] == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "scope": "https://outlook.office365.com/.default",
        "grant_type": "client_credentials",
    }
    assert observed["auth"] == (
        "XOAUTH2",
        "user=talentos@example.com\x01auth=Bearer access-token\x01\x01",
    )
    assert observed["from"] == "talentos@example.com"
    assert observed["to"] == "candidate@example.com"
    assert observed["body"].strip() == "Link"
    assert 'cid:tgpm-logo' in observed["html"]
    assert observed["logo"]


def test_refresh_token_flow_and_manual_access_token(monkeypatch):
    observed = {}
    cfg = SimpleNamespace(tenant_id="tenant", client_id="client", client_secret="secret", refresh_token="refresh", access_token="")

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "renewed-access"}

    def post(url, *, data, timeout):
        observed.update(data)
        return Response()

    monkeypatch.setattr(delivery.httpx, "post", post)
    assert delivery.smtp_access_token(cfg, None) == "renewed-access"
    assert observed["grant_type"] == "refresh_token" and observed["refresh_token"] == "refresh"
    cfg.refresh_token, cfg.client_secret, cfg.access_token = "", "", "manual-access"
    monkeypatch.setattr(delivery.httpx, "post", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Unexpected token call")))
    assert delivery.smtp_access_token(cfg, None) == "manual-access"


def test_local_test_email_cannot_be_sent_by_real_account(monkeypatch):
    import pytest

    from app.core.errors import DomainError

    monkeypatch.setattr(delivery, "smtp_runtime", lambda _: SimpleNamespace(enabled=True, test_mode=False))
    with pytest.raises(DomainError, match="EMAIL_MODE_CHANGED_DISABLED"):
        delivery.send_email({"delivery_mode": "test"}, "old-local-email")
