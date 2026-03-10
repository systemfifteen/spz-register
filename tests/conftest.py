import os
import pytest
import httpx

BASE_URL = os.getenv("TEST_URL", "https://spz.poetika.online")
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "")

TEST_EMAIL = "test.auto@spz.test"
TEST_PASSWORD = "AutoTest123!"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def admin_client():
    client = httpx.Client(base_url=BASE_URL)
    r = client.post("/token", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login zlyhal: {r.text}"
    yield client
    client.close()


@pytest.fixture(scope="session")
def test_user(admin_client):
    # Vytvor testovacieho používateľa
    admin_client.post("/admin/users", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    users = admin_client.get("/admin/users").json()
    user_id = next((u["id"] for u in users if u["email"] == TEST_EMAIL), None)
    assert user_id, "Test používateľ nebol vytvorený"
    yield {"email": TEST_EMAIL, "password": TEST_PASSWORD, "id": user_id}
    # Cleanup
    admin_client.request("DELETE", "/admin/users", json=[user_id])


@pytest.fixture(scope="session")
def user_client(test_user):
    client = httpx.Client(base_url=BASE_URL)
    r = client.post("/token", data={"username": test_user["email"], "password": test_user["password"]})
    assert r.status_code == 200, "Test user login zlyhal"
    yield client
    client.close()
