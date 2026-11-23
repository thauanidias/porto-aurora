from test_integration import call, register_candidate, setup_vacancy
from test_profile_photo import photo_bytes


def test_candidate_document_history_pagination_and_access(client, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    owner, candidate, _ = register_candidate(client, notice)
    other, _, _ = register_candidate(client, notice)
    call(client, "post", "/candidates/" + candidate["id"] + "/approve-document-uploads", actors["admin"]["headers"])
    application = call(client, "post", "/applications", owner, {
        "vacancy_id": vacancy["id"], "notice_id": notice["id"], "consent": True,
        "answers": {"interest": "Participar da seleção"},
    }, 201)
    baseline = call(client, "get", "/documents?include_photo=true", owner)["items"]
    uploaded = []
    for kind in ["CURRICULO", "CURRICULO", "CERTIFICADO", "PRE_ADMISSION", "FOTO_PERFIL"]:
        photo = kind == "FOTO_PERFIL"
        content = photo_bytes() if photo else b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n"
        data = {"type_name": kind}
        if kind == "PRE_ADMISSION":
            data["application_id"] = application["id"]
        response = client.post("/api/v1/documents", headers=owner, data=data,
            files={"file": ("foto.png" if photo else "arquivo.pdf", content,
                            "image/png" if photo else "application/pdf")})
        assert response.status_code == 201, response.text
        uploaded.append(response.json())
    assert uploaded[1]["revision"] == uploaded[0]["revision"] + 1
    assert call(client, "get", "/documents", owner)["total"] == 4 + len(baseline)
    found = []
    for number in [1, 2, 3]:
        result = call(client, "get", f"/documents?include_photo=true&page_size=2&page_number={number}", owner)
        assert result["total"] == 5 + len(baseline)
        assert result["page"] == number
        found.extend(row["id"] for row in result["items"])
        assert all("storage_key" not in row for row in result["items"])
    assert set(found) == {row["id"] for row in uploaded + baseline}
    assert len(found) == 5 + len(baseline)
    for row in uploaded:
        path = "/api/v1/documents/" + row["id"] + "/download"
        assert client.get(path, headers=owner).status_code == 200
        assert client.get(path, headers=other).status_code == 403
    assert call(client, "get", "/documents?include_photo=true", other)["total"] == 0
    assert client.get("/api/v1/documents?include_photo=true&candidate_id=" + candidate["id"], headers=other).status_code == 403
    assert client.get("/api/v1/documents?page_number=0", headers=owner).status_code == 422
