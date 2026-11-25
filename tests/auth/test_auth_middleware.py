import asyncio

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from llm_gateway.auth.key_store import VirtualKeyStore
from llm_gateway.security.auth import APIKeyAuthMiddleware, require_admin_api_key


def build_app(store):
    app = FastAPI()
    app.add_middleware(
        APIKeyAuthMiddleware,
        exclude_paths={"/health", "/admin"},
        key_store=store,
    )

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.post("/generate")
    async def generate(request: Request):
        return {
            "tenant_id": request.state.tenant_id,
            "key_id": request.state.key_id,
            "scopes": list(request.state.scopes),
            "rpm_limit": request.state.rpm_limit,
        }

    @app.get("/v1/costs")
    async def costs(request: Request):
        return {"tenant_id": request.state.tenant_id}

    @app.get("/admin/test", dependencies=[Depends(require_admin_api_key)])
    async def admin():
        return {"ok": True}

    return app


@pytest.fixture
def auth(tmp_path, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("ALLOW_DEMO_KEYS", "false")
    store = VirtualKeyStore(str(tmp_path / "keys.sqlite3"))
    return TestClient(build_app(store)), store


def headers(api_key):
    return {"Authorization": f"Bearer {api_key}"}


def test_health_is_excluded_from_auth(auth):
    client, _ = auth
    assert client.get("/health").status_code == 200


def test_valid_virtual_key_attaches_metadata(auth):
    client, store = auth
    raw_key, key = asyncio.run(
        store.create_key("tenant-a", scopes=("generate",), rpm_limit=25)
    )

    response = client.post("/generate", headers=headers(raw_key))

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant-a",
        "key_id": key.key_id,
        "scopes": ["generate"],
        "rpm_limit": 25,
    }


def test_unknown_key_is_rejected_in_production_mode(auth):
    client, _ = auth
    assert client.post("/generate", headers=headers("sk-unknown")).status_code == 401


def test_missing_scope_returns_forbidden(auth):
    client, store = auth
    raw_key, _ = asyncio.run(store.create_key("tenant-a", scopes=("costs",)))

    assert client.post("/generate", headers=headers(raw_key)).status_code == 403
    assert client.get("/v1/costs", headers=headers(raw_key)).status_code == 200


def test_revoked_key_is_rejected(auth):
    client, store = auth
    raw_key, _ = asyncio.run(store.create_key("tenant-a"))
    asyncio.run(store.revoke_key(raw_key))

    assert client.post("/generate", headers=headers(raw_key)).status_code == 401


def test_admin_scope_is_required(auth):
    client, store = auth
    generate_key = asyncio.run(store.create_key("tenant-a", scopes=("generate",)))
    admin_key = asyncio.run(store.create_key("tenant-a", scopes=("admin",)))

    assert (
        client.get("/admin/test", headers=headers(generate_key[0])).status_code == 403
    )
    assert client.get("/admin/test", headers=headers(admin_key[0])).status_code == 200


def test_demo_mode_preserves_tenant_mapping(tmp_path, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("ALLOW_DEMO_KEYS", "true")
    store = VirtualKeyStore(str(tmp_path / "keys.sqlite3"))
    app = FastAPI()
    app.add_middleware(
        APIKeyAuthMiddleware,
        exclude_paths={"/health"},
        tenant_map={"sk-demo": "demo-tenant"},
        key_store=store,
    )

    @app.post("/generate")
    async def generate(request: Request):
        return {"tenant_id": request.state.tenant_id, "key_id": request.state.key_id}

    with TestClient(app) as client:
        response = client.post("/generate", headers=headers("sk-demo"))
    assert response.status_code == 200
    assert response.json() == {"tenant_id": "demo-tenant", "key_id": "demo"}
