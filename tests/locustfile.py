"""
Záťažový test SPZ Register.

Spustenie (web UI na http://localhost:8089):
    locust -f tests/locustfile.py --host https://spz.poetika.online

Spustenie bez UI (headless):
    locust -f tests/locustfile.py --host https://spz.poetika.online \
        --headless -u 20 -r 2 --run-time 60s

Env vars:
    TEST_ADMIN_EMAIL    - email admina
    TEST_ADMIN_PASSWORD - heslo admina
    TEST_USER_EMAIL     - email testovacieho usera (vytvorený cez pytest alebo manuálne)
    TEST_USER_PASSWORD  - heslo testovacieho usera (default: AutoTest123!)
"""
import os
import random
import string

from locust import HttpUser, between, task

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "")
USER_EMAIL = os.getenv("TEST_USER_EMAIL", "test.auto@spz.test")
USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "AutoTest123!")

DISTRICTS = ["BA", "BB", "KE", "NR", "PO", "TN", "TT", "ZA", "ZI"]


def random_spz():
    prefix = random.choice(DISTRICTS)
    suffix = random.choice(DISTRICTS)
    number = random.randint(100, 999)
    return f"{prefix}{number}{suffix}"


class RegularUser(HttpUser):
    """Simuluje bežného používateľa — prihlásenie, vozidlá, povolenie."""

    weight = 4
    wait_time = between(1, 4)

    def on_start(self):
        self.client.post(
            "/token",
            data={"username": USER_EMAIL, "password": USER_PASSWORD},
        )

    @task(4)
    def list_vehicles(self):
        self.client.get("/vehicles")

    @task(3)
    def get_me(self):
        self.client.get("/me")

    @task(2)
    def check_permission(self):
        with self.client.get("/permissions", catch_response=True) as r:
            # 404 je OK — test user nemusí mať povolenie
            if r.status_code in (200, 404):
                r.success()

    @task(1)
    def add_and_delete_vehicle(self):
        spz = random_spz()
        r = self.client.post("/vehicles", json={"spz": spz})
        if r.status_code == 200:
            vid = r.json().get("id")
            if vid:
                self.client.delete(f"/vehicles/{vid}")

    def on_stop(self):
        self.client.post("/logout")


class AdminUser(HttpUser):
    """Simuluje admina — prehľad používateľov, export."""

    weight = 1
    wait_time = between(3, 8)

    def on_start(self):
        r = self.client.post(
            "/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        self.logged_in = r.status_code == 200

    @task(4)
    def list_users(self):
        if self.logged_in:
            self.client.get("/admin/users")

    @task(2)
    def list_all_vehicles(self):
        if self.logged_in:
            self.client.get("/admin/vehicles")

    @task(1)
    def export_csv(self):
        if self.logged_in:
            self.client.get("/admin/export")

    def on_stop(self):
        self.client.post("/logout")
