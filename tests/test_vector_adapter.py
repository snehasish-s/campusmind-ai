"""Exercise real Qdrant filtering in process; test vectors are not model-quality evidence."""

import numpy as np
from qdrant_client import QdrantClient
from app.config import settings
from app.intelligence import retrieval
from conftest import login, secure
from test_intelligence import post


class TestVectors:
    def encode(self, text, **kwargs):
        return np.array([[1.0, 0.0] for _ in text]) if isinstance(text, list) else np.array([1.0, 0.0])


def test_vector_tenant_filter_and_revalidated_approval(setup, monkeypatch):
    client, password, _, ids = setup
    vector_store = QdrantClient(":memory:")
    monkeypatch.setattr(settings(), "embedding_mode", "sentence_transformers")
    monkeypatch.setattr(retrieval, "embedding_model", lambda: TestVectors())
    monkeypatch.setattr(retrieval, "vector_client", lambda: vector_store)

    def upload(tenant):
        login(client, password, institution=tenant, identifier="ADMIN")
        d = client.post(
            "/api/evidence/documents",
            files={"file": ("evidence.txt", f"Faculty workshop evidence from fictional {tenant} college.".encode())},
            data={"title": f"{tenant} workshop"},
            headers=secure(client),
        )
        assert d.status_code == 200, d.text
        assert d.json()["index_status"] == "vector_and_keyword"
        assert (
            client.put(
                f"/api/evidence/documents/{d.json()['id']}/review",
                json={"status": "approved", "note": "Source reviewed for this synthetic test."},
                headers=secure(client),
            ).status_code
            == 200
        )
        return d.json()["id"]

    alpha = upload("alpha")
    beta = upload("beta")
    answer = post(client, "/evidence/ask", {"question": "faculty workshop"})
    assert {s["document_id"] for s in answer["sources"]} == {beta}
    assert answer["retrieval_method"] == "hybrid_rrf"
    # Stale indexed vectors cannot bypass the current document approval state.
    assert (
        client.put(
            f"/api/evidence/documents/{beta}/review",
            json={"status": "rejected", "note": "Withdrawn after source review."},
            headers=secure(client),
        ).status_code
        == 200
    )
    assert post(client, "/evidence/ask", {"question": "faculty workshop"})["sources"] == []
    login(client, password, identifier="ADMIN")
    assert {s["document_id"] for s in post(client, "/evidence/ask", {"question": "faculty workshop"})["sources"]} == {alpha}
    assert client.delete(f"/api/evidence/documents/{alpha}", headers=secure(client)).status_code == 200
    assert post(client, "/evidence/ask", {"question": "faculty workshop"})["sources"] == []
    vector_store.close()
