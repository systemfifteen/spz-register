"""
Regresné testy k bezpečnostnému auditu (Hermes, run-1, dávka A).

Bežia LOKÁLNE v procese nad dočasnou SQLite – nikdy nie proti produkcii (na rozdiel od test_api.py):
    pip install -r requirements.txt -r tests/requirements.txt
    pytest tests/test_security.py -v
"""
import csv
import io
import os
import sqlite3

import pytest

os.environ.setdefault("SECRET_KEY", "test-only-secret")
os.environ.setdefault("RATE_LIMIT_LOGIN", "1000/minute")

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, create_engine  # noqa: E402

import main  # noqa: E402

ADMIN = ("admin@spz.test", "AdminHeslo123")
USER = ("user@spz.test", "UserHeslo123")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "engine", create_engine(f"sqlite:///{tmp_path}/db.sqlite"))
    main.limiter.enabled = False
    with TestClient(main.app, base_url="https://testserver") as c:  # lifespan: create_all + migrate
        with Session(main.engine) as s:
            s.add(main.User(email=ADMIN[0], hashed_password=main.pwd_context.hash(ADMIN[1]), is_admin=True))
            s.add(main.User(email=USER[0], hashed_password=main.pwd_context.hash(USER[1])))
            s.commit()
        yield c
    main.limiter.enabled = True


def login(app, email, password):
    c = TestClient(main.app, base_url="https://testserver")
    r = c.post("/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return c


def token_of(c):
    return c.cookies.get("access_token")


def bearer(app, token):
    return app.get("/me", headers={"Authorization": f"Bearer {token}"}, cookies={})


# ── JWT revokácia ──────────────────────────────────────────────────────────

def test_old_token_rejected_after_logout(app):
    c = login(app, *USER)
    old = token_of(c)
    assert bearer(app, old).status_code == 200
    assert c.post("/logout").status_code == 200
    assert bearer(app, old).status_code == 401


def test_old_token_rejected_after_password_change_but_this_session_continues(app):
    c, other = login(app, *USER), login(app, *USER)
    old = token_of(other)
    r = c.post("/change-password", json={"old_password": USER[1], "new_password": "NoveHeslo456"})
    assert r.status_code == 200
    assert bearer(app, old).status_code == 401           # iné zariadenie odhlásené
    assert c.get("/me").status_code == 200               # toto dostalo nový cookie
    login(app, USER[0], "NoveHeslo456")


def test_old_token_rejected_after_password_reset(app):
    c = login(app, *USER)
    old = token_of(c)
    with Session(main.engine) as s:
        uid = s.exec(main.select(main.User).where(main.User.email == USER[0])).one().id
        s.add(main.PasswordResetToken(token="t0k3n", user_id=uid,
                                      expires_at=main.datetime.utcnow() + main.timedelta(hours=1)))
        s.commit()
    assert app.post("/reset-password", json={"token": "t0k3n", "new_password": "ResetHeslo789"}).status_code == 200
    assert bearer(app, old).status_code == 401


def test_token_without_version_claim_still_valid_for_existing_sessions(app):
    """Tokeny vydané pred nasadením nemajú "tv" – nesmú všetkých odhlásiť."""
    with Session(main.engine) as s:
        uid = s.exec(main.select(main.User).where(main.User.email == USER[0])).one().id
    legacy = main.jwt.encode({"sub": uid, "exp": main.datetime.utcnow() + main.timedelta(hours=1)},
                             main.SECRET_KEY, algorithm=main.ALGORITHM)
    assert bearer(app, legacy).status_code == 200


def test_migration_adds_column_to_old_database(tmp_path):
    db = tmp_path / "old.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE user (id TEXT PRIMARY KEY, email TEXT, hashed_password TEXT, is_admin BOOLEAN, "
                "login_count INTEGER DEFAULT 0 NOT NULL, last_login TEXT)")
    con.execute("INSERT INTO user VALUES ('u1', 'a@b.sk', 'x', 0, 3, NULL)")
    con.commit()
    con.close()
    engine = create_engine(f"sqlite:///{db}")
    main.migrate(engine)
    main.migrate(engine)  # idempotentné
    with Session(engine) as s:
        assert s.get(main.User, "u1").token_version == 0


# ── Heslá ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("new", ["kratke", "x" * 73, "č" * 37])  # 37 × 2 bajty = 74
def test_change_password_length_limits(app, new):
    c = login(app, *USER)
    r = c.post("/change-password", json={"old_password": USER[1], "new_password": new})
    assert r.status_code == 422
    login(app, *USER)  # heslo sa nezmenilo


def test_too_long_password_is_401_not_500(app):
    c = TestClient(main.app, base_url="https://testserver")
    assert c.post("/token", data={"username": USER[0], "password": "x" * 200}).status_code == 401


def test_register_and_reset_reject_too_long_password(app):
    assert app.post("/register", json={"email": "n@spz.test", "password": "x" * 80}).status_code == 422
    assert app.post("/reset-password", json={"token": "t", "new_password": "x" * 80}).status_code == 422


# ── Email (XSS / CSV) ──────────────────────────────────────────────────────

@pytest.mark.parametrize("email", ['<img src=x onerror=alert(1)>@a.sk', 'a"b@a.sk', "a'b@a.sk", "a b@a.sk",
                                   "=cmd@a.sk", "+1@a.sk", "-1@a.sk", "@a.sk", "a@a", "a@<b>.sk"])
def test_register_rejects_dangerous_email(app, email):
    assert app.post("/register", json={"email": email, "password": "DobreHeslo1"}).status_code == 422


def test_register_accepts_normal_email(app):
    r = app.post("/register", json={"email": "  Jana.Novakova+spz@Mesto-BB.sk ", "password": "DobreHeslo1"})
    assert r.status_code == 200
    login(app, "jana.novakova+spz@mesto-bb.sk", "DobreHeslo1")


def test_import_rejects_dangerous_email(app):
    admin = login(app, *ADMIN)
    r = admin.post("/admin/import", json=[["=HYPERLINK(\"x\")@a.sk", "DobreHeslo1"], ["ok@spz.test", "DobreHeslo1"]])
    assert r.status_code == 200 and len(r.json()["invalid"]) == 1


def test_csv_export_neutralizes_formulas(app):
    admin = login(app, *ADMIN)
    with Session(main.engine) as s:  # stará hodnota v DB (spred validácie) + vzorec v okne povolenia
        s.add(main.User(id="old", email="=1+1@a.sk", hashed_password="x"))
        s.add(main.Permission(user_id="old", daily_entries=1, time_window="@SUM(A1)"))
        s.commit()
    rows = list(csv.reader(io.StringIO(admin.get("/admin/export").text)))
    old = next(r for r in rows if r[1] == "old")
    assert old[0] == "'=1+1@a.sk" and old[4] == "'@SUM(A1)"
    assert any(r[0] == USER[0] for r in rows)  # bežné hodnoty bez zmeny


# ── Frontend ───────────────────────────────────────────────────────────────

def test_frontend_escapes_and_hides_reset_token():
    html = open(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"), encoding="utf-8").read()
    assert 'data-exclude-search="true"' in html
    assert "Content-Security-Policy" in html
    script = html.split("const API_BASE", 1)[1]
    assert script.index("history.replaceState(null, '', '/')") < script.index("function checkAuth")
    for raw in ("${u.email}", "${u.time_window}", "${perm.time_window}", "${v.spz}", "${message}", "onclick=\"delete"):
        assert raw not in html, raw
