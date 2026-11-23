import base64
import io
import xml.etree.ElementTree as ET
import zipfile

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from test_candidate_journey import advance, enroll, journey_owner  # noqa: F401

from app.core.config import settings
from app.models import AuthSession, Candidate, Consent, ConsentReceipt, Outbox, User
from app.services.receipt_document import SOURCE


def signature_image():
    image = Image.new("RGB", (900, 220), "white")
    ImageDraw.Draw(image).line((30, 120, 250, 50, 450, 140), fill="black", width=4)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()



def test_signup_acceptance_is_available_before_selection_phase(client, db, monkeypatch, journey_owner):  # noqa: F811
    monkeypatch.setattr(settings(), "email_verification_required", False)
    email = "profile-consent@example.com"
    response = client.post("/api/v1/auth/register", json={
        "name": "Profile Candidate", "email": email,
        "consent": False, "defer_consent_to_profile": True,
    })
    assert response.status_code == 201, response.text
    candidate = db.scalar(select(Candidate).where(Candidate.email == email))
    assert db.scalar(select(Consent.id).where(Consent.candidate_id == candidate.id)) is None
    assert db.scalar(select(ConsentReceipt.id).where(ConsentReceipt.email == email)) is None
    token = response.json()["test_setup_url"].split("#token=", 1)[1].split("&", 1)[0]
    confirmed = client.post("/api/v1/auth/consume-link", json={"token": token, "password": "Pt42!?"})
    assert confirmed.status_code == 200, confirmed.text
    headers = {"Authorization": "Bearer " + confirmed.json()["access_token"]}
    first_acceptance = client.post("/api/v1/public/consent-receipts", headers=headers, json={
        "name": "Profile Candidate", "email": email, "context": "CADASTRO", "accepted": True, "read_to_end": True,
    })
    assert first_acceptance.status_code == 201, first_acceptance.text
    _, job, admin, _ = journey_owner
    application = enroll(client, headers, job)
    advance(client, admin, application, job, "SELECTION")
    accepted = client.post("/api/v1/public/consent-receipts", headers=headers, json={
        "name": "Profile Candidate", "email": email, "context": "CADASTRO", "accepted": True, "signature_image": signature_image(),
    })
    assert accepted.status_code == 201, accepted.text
    consent = db.scalar(select(Consent).where(Consent.candidate_id == candidate.id).order_by(Consent.created_at.desc()))
    assert consent.granted is True
    assert consent.notice_snapshot["receipt_id"] == accepted.json()["id"]
    assert client.get("/api/v1/privacy/consent-receipts/" + accepted.json()["id"] + "/document", headers=headers).status_code == 200


def test_receipt_is_immediate_and_private(client, db, actors):
    response = client.post(
        "/api/v1/public/consent-receipts",
        json={
            "name": "Pessoa de Teste",
            "email": "receipt@example.com",
            "context": "CADASTRO",
            "accepted": True, "signature_image": signature_image(),
        },
        headers={"X-Real-IP": "203.0.113.99"},
    )
    assert response.status_code == 201, response.text
    receipt = response.json()
    download = client.get(receipt["download_url"])
    assert download.status_code == 200
    assert client.get(receipt["download_url"].replace("token=", "token=invalid")).status_code == 403
    assert receipt["protocol"].startswith("TGPM-ACEITE-")
    assert receipt["created_at"]
    assert receipt["ip"] == "testclient"  # Untrusted header cannot forge the origin.
    assert len(receipt["document_sha256"]) == 64
    assert client.get("/api/v1/privacy/consent-receipts").status_code == 401
    assert (
        client.get(
            "/api/v1/privacy/consent-receipts", headers=actors["manager"]["headers"]
        ).status_code
        == 403
    )
    detail = client.get(
        "/api/v1/privacy/consent-receipts/" + receipt["id"], headers=actors["admin"]["headers"]
    )
    assert detail.status_code == 200
    assert "Cláusula Oitava" in "\n".join(detail.json()["document_snapshot"]["paragraphs"])
    document = client.get(
        "/api/v1/privacy/consent-receipts/" + receipt["id"] + "/document",
        headers=actors["admin"]["headers"],
    )
    assert document.status_code == 200
    assert document.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    with (
        zipfile.ZipFile(io.BytesIO(document.content)) as delivered,
        zipfile.ZipFile(SOURCE) as original,
    ):
        assert delivered.testzip() is None
        assert set(delivered.namelist()) == set(original.namelist()) | {"word/media/consent-signature.png"}
        assert delivered.read("word/styles.xml") == original.read("word/styles.xml")
        document_xml = delivered.read("word/document.xml").decode("utf-8")
        ET.fromstring(document_xml)
        assert "TERMO DE CONSENTIMENTO" in document_xml
        assert receipt["protocol"] in document_xml
        assert receipt["ip"] in document_xml
        assert "Assinatura eletrônica" in document_xml
        assert "Assinado eletronicamente por" in document_xml
        assert receipt["name"] in document_xml
        assert "Barcarena/PA" not in document_xml
        assert "Assinatura do candidato" not in document_xml
        assert b'<wp:positionV relativeFrom="page">' in delivered.read("word/footer1.xml")
    assert (
        client.get(
            "/api/v1/privacy/consent-receipts/" + receipt["id"] + "/document",
            headers=actors["manager"]["headers"],
        ).status_code
        == 403
    )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE consent_receipts SET ip='changed' WHERE id=:id"), {"id": receipt["id"]}
        )


def test_authenticated_identity_and_explicit_acceptance(client, db, actors):
    body = {
        "name": "Outro Nome",
        "email": "other@example.com",
        "context": "CANDIDATURA",
        "accepted": True, "signature_image": signature_image(),
    }
    response = client.post(
        "/api/v1/public/consent-receipts", json=body, headers=actors["admin"]["headers"]
    )
    assert response.status_code == 201
    assert response.json()["email"] == actors["admin"]["email"]
    row = db.scalar(select(ConsentReceipt).where(ConsentReceipt.id == response.json()["id"]))
    assert row.user_id == actors["admin"]["id"]
    body["accepted"] = False
    assert client.post("/api/v1/public/consent-receipts", json=body).status_code == 422


def test_register_without_verification_during_tests(client, db, monkeypatch):
    monkeypatch.setattr(settings(), "email_verification_required", False)
    body = {
        "name": "Pessoa Teste Livre",
        "email": "testing-signup@example.com",
        "context": "CADASTRO",
        "accepted": True, "signature_image": signature_image(),
    }
    receipt = client.post("/api/v1/public/consent-receipts", json=body).json()
    signup = {
        "name": body["name"],
        "email": body["email"],
        "consent": True,
        "receipt_id": receipt["id"],
    }
    response = client.post("/api/v1/auth/register", json=signup)
    assert response.status_code == 201, response.text
    assert "access_token" not in response.json()
    token = response.json()["test_setup_url"].split("#token=", 1)[1].split("&", 1)[0]
    password = "St42!?"
    assert client.post(
        "/api/v1/auth/login", json={"email": body["email"], "password": password}
    ).status_code == 401
    confirmed = client.post(
        "/api/v1/auth/consume-link", json={"token": token, "password": password}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["user"]["email_verified"]
    headers = {"Authorization": "Bearer " + confirmed.json()["access_token"]}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": body["email"], "password": password}
        ).status_code
        == 200
    )
    assert (
        db.scalar(select(Outbox.id).where(Outbox.payload["recipient"].astext == body["email"]))
        is None
    )
    monkeypatch.setattr(settings(), "email_verification_required", True)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_register_with_document_receipt_without_published_notice(client, db, monkeypatch):
    monkeypatch.setattr(settings(), "email_verification_required", True)
    body = {
        "name": "Pessoa Cadastro",
        "email": "signup-receipt@example.com",
        "context": "CADASTRO",
        "accepted": True, "signature_image": signature_image(),
    }
    receipt = client.post("/api/v1/public/consent-receipts", json=body).json()
    signup = {
        "name": body["name"],
        "email": body["email"],
        "consent": True,
        "receipt_id": receipt["id"],
    }
    wrong = {**signup, "email": "different@example.com"}
    assert client.post("/api/v1/auth/register", json=wrong).status_code == 422
    response = client.post("/api/v1/auth/register", json=signup)
    assert response.status_code == 201, response.text
    assert response.json()["verification_required"]
    assert "access_token" not in response.json()
    assert "tgpm_refresh" not in response.cookies
    user = db.scalar(select(User).where(User.email == body["email"]))
    assert not user.email_verified
    assert db.scalar(select(AuthSession.id).where(AuthSession.user_id == user.id)) is None
    login = {"email": body["email"], "password": "St42!?"}
    blocked = client.post("/api/v1/auth/login", json=login)
    assert blocked.status_code == 401
    token = response.json()["test_setup_url"].split("#token=", 1)[1].split("&", 1)[0]
    assert client.post("/api/v1/auth/consume-link", json={"token": token}).status_code == 422
    confirmed = client.post(
        "/api/v1/auth/consume-link", json={"token": token, "password": login["password"]}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["user"]["email_verified"]
    headers = {"Authorization": "Bearer " + confirmed.json()["access_token"]}
    own_list = client.get("/api/v1/privacy/my-consent-receipts", headers=headers)
    assert own_list.status_code == 200
    assert receipt["id"] in {row["id"] for row in own_list.json()["items"]}
    own_detail = client.get("/api/v1/privacy/consent-receipts/" + receipt["id"], headers=headers)
    assert own_detail.status_code == 200
    assert own_detail.json()["document_snapshot"]["paragraphs"]
    own_document = client.get(
        "/api/v1/privacy/consent-receipts/" + receipt["id"] + "/document",
        headers=headers,
    )
    assert own_document.status_code == 200
    assert own_document.content.startswith(b"PK")
    unlinked = client.post(
        "/api/v1/public/consent-receipts", json={**body, "name": "Outra Pessoa"}
    ).json()
    assert (
        client.get(
            "/api/v1/privacy/consent-receipts/" + unlinked["id"], headers=headers
        ).status_code
        == 404
    )
    after = client.get("/api/v1/privacy/my-consent-receipts", headers=headers).json()
    assert unlinked["id"] not in {row["id"] for row in after["items"]}
    assert client.post("/api/v1/auth/consume-link", json={"token": token}).status_code == 400
    assert client.post("/api/v1/auth/login", json=login).status_code == 200
    consent = db.scalar(
        select(Consent).where(Consent.notice_snapshot["receipt_id"].astext == receipt["id"])
    )
    assert consent.notice_id is None
    assert consent.notice_snapshot["receipt_protocol"] == receipt["protocol"]
    assert (
        client.post(
            "/api/v1/auth/register",
            json={**signup, "receipt_id": None, "email": "missing-receipt@example.com"},
        ).status_code
        == 422
    )


def test_signature_required_and_blank_rejected(client):
    body = {"name": "Pessoa Teste", "email": "signature@example.com", "context": "CADASTRO", "accepted": True}
    assert client.post("/api/v1/public/consent-receipts", json=body).status_code == 422
    body["signature_image"] = "data:image/png;base64,aW52YWxpZA=="
    assert client.post("/api/v1/public/consent-receipts", json=body).status_code == 422
