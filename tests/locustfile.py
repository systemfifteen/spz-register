"""
Záťažový test SPZ Register.

Spustenie (web UI na http://localhost:8089):
    locust -f tests/locustfile.py --host https://spz.poetika.online

Spustenie bez UI (headless):
    locust -f tests/locustfile.py --host https://spz.poetika.online \
        --headless -u 20 -r 2 --run-time 60s

Env vars:
    TEST_ADMIN_EMAIL    - email admina (povinné)
    TEST_ADMIN_PASSWORD - heslo admina (povinné)

Poznámka: Pred spustením testu sa vytvorí pool dočasných účtov (locust-*@spz.test)
cez jediný admin session, aby sa predišlo rate-limitingu na /token.
Na konci sa všetky dočasné účty zmažú dávkovo.
"""
import os
import random
import secrets
from queue import Empty, Queue

import httpx
from locust import HttpUser, between, events, task

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "")

DISTRICTS = ["BA", "BB", "KE", "NR", "PO", "TN", "TT", "ZA", "ZI"]
LOCUST_PASSWORD = "LocustTest123!"

_user_pool: Queue = Queue()
_created_user_ids: list[str] = []


def random_spz():
    prefix = random.choice(DISTRICTS)
    suffix = random.choice(DISTRICTS)
    number = random.randint(100, 999)
    return f"{prefix}{number}{suffix}"


@events.init.add_listener
def create_test_user_pool(environment, **kwargs):
    """Vytvorí pool dočasných účtov pred štartom testu (jeden admin session)."""
    host = environment.host or "https://spz.poetika.online"
    num_users = getattr(environment.parsed_options, "num_users", 10)

    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("[pool] TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD nie sú nastavené, preskakujem.")
        return

    print(f"[pool] Vytváram {num_users} dočasných locust účtov...")
    with httpx.Client(base_url=host) as admin:
        r = admin.post("/token", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if r.status_code != 200:
            print(f"[pool] Admin login zlyhal ({r.status_code}), test nebude fungovať.")
            return

        for _ in range(num_users):
            email = f"locust-{secrets.token_hex(6)}@spz.test"
            r = admin.post("/admin/users", json={"email": email, "password": LOCUST_PASSWORD})
            if r.status_code == 200:
                _user_pool.put({"email": email, "password": LOCUST_PASSWORD})

        # Zisti ID všetkých vytvorených účtov
        all_users = admin.get("/admin/users").json()
        for u in all_users:
            if u["email"].startswith("locust-") and u["email"].endswith("@spz.test"):
                _created_user_ids.append(u["id"])

        admin.post("/logout")

    print(f"[pool] Pool pripravený: {_user_pool.qsize()} účtov.")


@events.quitting.add_listener
def cleanup_test_user_pool(environment, **kwargs):
    """Zmaže všetky dočasné locust-* účty po skončení testu."""
    if not _created_user_ids:
        return
    import time
    host = environment.host or "https://spz.poetika.online"
    print(f"[pool] Mažem {len(_created_user_ids)} dočasných locust účtov...")
    with httpx.Client(base_url=host) as admin:
        # Retry admin login — po ukončení testu môže byť rate limit ešte aktívny
        for attempt in range(5):
            r = admin.post("/token", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            if r.status_code == 200:
                break
            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"[pool] Admin login rate-limitovaný, čakám {wait}s (pokus {attempt + 1}/5)...")
                time.sleep(wait)
            else:
                print(f"[pool] Admin login zlyhal ({r.status_code}), cleanup preskakujem.")
                return
        else:
            print("[pool] Admin login sa nepodaril po 5 pokusoch, cleanup preskakujem.")
            return
        r = admin.request("DELETE", "/admin/users", json=_created_user_ids)
        print(f"[pool] Cleanup hotový (status {r.status_code}).")
        admin.post("/logout")


class RegularUser(HttpUser):
    """Simuluje bežného používateľa — prihlásenie, vozidlá, povolenie."""

    weight = 4
    wait_time = between(1, 4)

    def on_start(self):
        try:
            creds = _user_pool.get_nowait()
        except Empty:
            print("[user] Pool je prázdny, user nebude aktívny.")
            self.logged_in = False
            return

        self.email = creds["email"]
        r = self.client.post(
            "/token",
            data={"username": self.email, "password": LOCUST_PASSWORD},
        )
        self.logged_in = r.status_code == 200

    @task(4)
    def list_vehicles(self):
        if self.logged_in:
            self.client.get("/vehicles")

    @task(3)
    def get_me(self):
        if self.logged_in:
            self.client.get("/me")

    @task(2)
    def check_permission(self):
        if not self.logged_in:
            return
        with self.client.get("/permissions", catch_response=True) as r:
            # 404 je OK — test user nemusí mať povolenie
            if r.status_code in (200, 404):
                r.success()

    @task(1)
    def add_and_delete_vehicle(self):
        if not self.logged_in:
            return
        spz = random_spz()
        r = self.client.post("/vehicles", json={"spz": spz})
        if r.status_code == 200:
            vid = r.json().get("id")
            if vid:
                self.client.delete(f"/vehicles/{vid}")

    def on_stop(self):
        if self.logged_in:
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
