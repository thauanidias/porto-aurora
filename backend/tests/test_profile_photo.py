import io

import pytest
from PIL import Image
from sqlalchemy import select
from test_integration import call, register_candidate, setup_vacancy

from app.core.errors import DomainError
from app.integrations.files import prepare_profile_photo
from app.models import Document, Outbox, PipelineStage, Vacancy


def photo_bytes(kind="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (1000, 600), "#a3181a").save(output, format=kind)
    return output.getvalue()


@pytest.mark.parametrize("kind", ["PNG", "JPEG", "WEBP"])
def test_photo_is_resized_and_reencoded(kind):
    result = prepare_profile_photo(photo_bytes(kind))
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "JPEG"
        assert image.size == (800, 480)
        assert not image.getexif()


@pytest.mark.parametrize("content", [b"fake image", b"<svg></svg>", b"x" * (5 * 1024 * 1024 + 1)])
def test_photo_rejects_invalid_or_oversized_input(content):
    with pytest.raises(DomainError):
        prepare_profile_photo(content)


def test_photo_owner_replacement_removal_and_blind_access(client, db, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    owner, candidate, _ = register_candidate(client, notice)
    other, _, _ = register_candidate(client, notice)
    admin = actors["admin"]["headers"]

    def upload():
        response = client.post("/api/v1/documents", headers=owner,
            data={"type_name": "FOTO_PERFIL"}, files={"file": ("photo.png", photo_bytes(), "image/png")})
        assert response.status_code == 201, response.text
        return response.json()

    first = upload()
    path = "/api/v1/documents/" + first["id"] + "/download"
    assert client.get(path, headers=owner).status_code == 200
    assert client.get(path, headers=admin).status_code == 200
    assert client.get(path, headers=other).status_code == 403
    assert client.get(path).status_code == 401
    assert call(client, "get", "/documents", owner)["total"] == 0
    second = upload()
    assert second["revision"] == 2
    assert client.get(path, headers=owner).status_code == 409
    assert db.scalar(select(Outbox).where(Outbox.dedup_key == "delete:" + first["id"]))
    assert call(client, "get", "/documents?type_name=FOTO_PERFIL", owner)["total"] == 1

    application = call(client, "post", "/applications", owner, {
        "vacancy_id": vacancy["id"], "notice_id": notice["id"], "consent": True,
        "answers": {"interest": "Participar da seleção"},
    }, 201)
    db.get(Vacancy, vacancy["id"]).blind = True
    db.get(PipelineStage, application["stage_id"]).reveal_identity = False
    db.commit()
    path = "/api/v1/documents/" + second["id"] + "/download"
    assert client.get(path, headers=admin).status_code == 403
    assert client.get("/api/v1/documents/admission-checklist?candidate_id=" + candidate["id"], headers=admin).status_code == 403
    assert call(client, "get", "/documents?type_name=FOTO_PERFIL&candidate_id=" + candidate["id"], admin)["total"] == 0
    assert client.get(path, headers=owner).status_code == 200
    call(client, "delete", "/candidates/me/photo", owner)
    assert call(client, "get", "/documents?type_name=FOTO_PERFIL", owner)["total"] == 0
    assert db.get(Document, second["id"]).scan_status == "DELETED"
    assert client.get(path, headers=owner).status_code == 409
