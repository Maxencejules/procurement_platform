import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app, get_db_session


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_graphql_endpoint_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/graphql")
        # GraphQL playground or 200 expected
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_login_invalid_credentials(session):
    async def test_session():
        yield session
    app.dependency_overrides[get_db_session] = test_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/graphql",
                json={"query": 'mutation { login(email: "nobody@test.com", password: "wrong") { token user { id } } }'},
            )
            assert response.status_code == 200
            assert response.json()["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_unauthenticated_query():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/graphql",
            json={
                "query": """
                    query {
                        purchaseRequests {
                            items { id }
                            total
                        }
                    }
                """
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("errors") is not None
