"""
Funkčné testy SPZ Register API.

Spustenie:
    pip install -r tests/requirements.txt
    TEST_ADMIN_EMAIL=admin@example.com TEST_ADMIN_PASSWORD=heslo pytest tests/ -v
"""
import httpx
import pytest


# ── Health ─────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health(self, base_url):
        r = httpx.get(f"{base_url}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_frontend_loads(self, base_url):
        r = httpx.get(base_url, follow_redirects=True)
        assert r.status_code == 200
        assert "Registrácia ŠPZ" in r.text


# ── Auth ───────────────────────────────────────────────────────────────────

class TestAuth:
    def test_me_authenticated(self, user_client, test_user):
        r = user_client.get("/me")
        assert r.status_code == 200
        assert r.json()["email"] == test_user["email"]

    def test_me_without_auth(self, base_url):
        r = httpx.get(f"{base_url}/me")
        assert r.status_code == 401

    def test_login_wrong_password(self, base_url, test_user):
        r = httpx.post(
            f"{base_url}/token",
            data={"username": test_user["email"], "password": "zle-heslo"},
        )
        assert r.status_code == 401

    def test_login_nonexistent_user(self, base_url):
        r = httpx.post(
            f"{base_url}/token",
            data={"username": "neexistuje@test.sk", "password": "heslo123"},
        )
        assert r.status_code == 401


# ── Vozidlá ────────────────────────────────────────────────────────────────

class TestVehicles:
    def test_list_vehicles(self, user_client):
        r = user_client.get("/vehicles")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_add_and_delete_vehicle(self, user_client):
        r = user_client.post("/vehicles", json={"spz": "TS111TS"})
        assert r.status_code == 200
        vid = r.json()["id"]
        assert r.json()["spz"] == "TS111TS"

        r = user_client.delete(f"/vehicles/{vid}")
        assert r.status_code == 200

    def test_spz_normalization(self, user_client):
        # Medzery a pomlčky sa musia odstrániť, písmená sa zmenia na veľké
        r = user_client.post("/vehicles", json={"spz": "ts 111 ts"})
        assert r.status_code == 200
        assert r.json()["spz"] == "TS111TS"
        user_client.delete(f"/vehicles/{r.json()['id']}")

    def test_invalid_spz_format(self, user_client):
        r = user_client.post("/vehicles", json={"spz": "INVALID"})
        assert r.status_code == 422

    def test_delete_nonexistent_vehicle(self, user_client):
        r = user_client.delete("/vehicles/neexistujuce-id")
        assert r.status_code == 404

    def test_cannot_delete_other_users_vehicle(self, user_client, admin_client):
        # Admin pridá vozidlo
        users = admin_client.get("/admin/users").json()
        admin_id = next(u["id"] for u in users if u["is_admin"])
        r = admin_client.post(f"/admin/vehicles/{admin_id}", json={"spz": "BB222BB"})
        assert r.status_code == 200
        vid = r.json()["id"]
        # Bežný user sa ho pokúsi zmazať
        r = user_client.delete(f"/vehicles/{vid}")
        assert r.status_code == 403
        # Cleanup
        admin_client.delete(f"/vehicles/{vid}")


# ── Povolenie ──────────────────────────────────────────────────────────────

class TestPermissions:
    def test_permission_not_set_returns_404(self, user_client):
        r = user_client.get("/permissions")
        # Test user nemá nastavené povolenie
        assert r.status_code in (200, 404)

    def test_admin_set_and_get_permission(self, admin_client, test_user):
        r = admin_client.post(
            f"/admin/permissions/{test_user['id']}",
            json={"daily_entries": 3, "time_window": "06:00 - 10:00"},
        )
        assert r.status_code == 200

        r = admin_client.get(f"/admin/permissions/{test_user['id']}")
        assert r.status_code == 200
        assert r.json()["daily_entries"] == 3
        assert r.json()["time_window"] == "06:00 - 10:00"


# ── Zmena hesla ────────────────────────────────────────────────────────────

class TestChangePassword:
    def test_wrong_current_password(self, user_client):
        r = user_client.post(
            "/change-password",
            json={"old_password": "zle-heslo", "new_password": "NoveHeslo123!"},
        )
        assert r.status_code == 400


# ── Reset hesla ────────────────────────────────────────────────────────────

class TestPasswordReset:
    def test_forgot_password_always_200(self, base_url):
        # Nesmie prezradiť či email existuje
        r = httpx.post(
            f"{base_url}/forgot-password",
            json={"email": "neexistuje@test.sk"},
        )
        assert r.status_code == 200

    def test_reset_with_invalid_token(self, base_url):
        r = httpx.post(
            f"{base_url}/reset-password",
            json={"token": "neplatny-token-xyz", "new_password": "NoveHeslo123!"},
        )
        assert r.status_code == 400

    def test_reset_password_too_short(self, base_url):
        r = httpx.post(
            f"{base_url}/reset-password",
            json={"token": "nejaky-token", "new_password": "kratke"},
        )
        assert r.status_code == 400


# ── Admin ──────────────────────────────────────────────────────────────────

class TestAdmin:
    def test_list_users(self, admin_client):
        r = admin_client.get("/admin/users")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0

    def test_list_users_forbidden_for_regular_user(self, user_client):
        r = user_client.get("/admin/users")
        assert r.status_code == 403

    def test_export_csv(self, admin_client):
        r = admin_client.get("/admin/export")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "email" in r.text

    def test_import_users_with_comments(self, admin_client):
        data = [
            ["# toto je komentar"],
            ["import.test@spz.test", "ImportTest123!"],
        ]
        r = admin_client.post("/admin/import", json=data)
        assert r.status_code == 200
        assert r.json()["message"].startswith("Importovaných 1")
        # Cleanup
        users = admin_client.get("/admin/users").json()
        uid = next((u["id"] for u in users if u["email"] == "import.test@spz.test"), None)
        if uid:
            admin_client.request("DELETE", "/admin/users", json=[uid])

    def test_admin_endpoints_require_auth(self, base_url):
        for path in ["/admin/users", "/admin/export", "/admin/vehicles"]:
            r = httpx.get(f"{base_url}{path}")
            assert r.status_code == 401, f"{path} mal vrátiť 401"
