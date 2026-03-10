# Registrácia ŠPZ – Pešia zóna Banská Bystrica

Webová aplikácia na správu vstupov vozidiel do pešej zóny mesta Banská Bystrica.

**Produkčné URL:** https://spz.poetika.online

---

## Funkcie

**Používateľské:**
- Prihlásenie cez httpOnly cookie (JWT, 8h platnosť)
- Registrácia a správa vlastných vozidiel (ŠPZ)
- Zobrazenie prideleného povolenia (počet vstupov, časové okno)
- Zmena hesla + reset hesla cez email
- Prepínanie jazyka SK / EN

**Administrátorské:**
- Správa používateľov — prehľad, vyhľadávanie, hromadné mazanie
- Zoskupenie používateľov podľa stavu prihlásenia
- Nastavenie povolení (počet vstupov denne, časové okno)
- Správa vozidiel za jednotlivých používateľov
- Import používateľov z CSV (podpora komentárov `#`)
- Export do CSV

**Technické:**
- Rate limiting (`/token` 5/min, `/register` 5/min, `/forgot-password` 3/min)
- Validácia formátu ŠPZ (`BA123AB`)
- Sila hesla (vizuálny indikátor)
- Prometheus metriky (`/metrics`)
- Denné SQLite zálohy s rotáciou 7 dní

---

## Tech stack

| Vrstva | Technológia |
|--------|-------------|
| Backend | FastAPI + SQLModel (SQLite) |
| Auth | python-jose (JWT) + passlib (bcrypt) |
| Frontend | Vanilla JS + Bootstrap 5.3 (single HTML) |
| Infra | Docker + Traefik (Coolify) |
| Monitoring | Prometheus + Grafana |

---

## Nasadenie (Coolify)

Aplikácia beží cez [Coolify](https://coolify.io) s Traefik reverse proxy.

Požadované env vars:

```
SECRET_KEY=            # povinné, min. 32 znakov
ALLOWED_ORIGINS=https://spz.poetika.online
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
RATE_LIMIT_LOGIN=5/minute   # rate limit na /token a /register (default: 5/minute)
```

### Lokálne (bez Coolify)

```bash
git clone https://github.com/systemfifteen/spz-register.git
cd spz-register
SECRET_KEY=lokalny-dev-kluc docker compose up -d --build
```

Aplikácia beží na `http://localhost:8000`.

---

## Prvý admin

```bash
docker exec -it <container> python3 scripts/create_admin_inline.py admin@example.com heslo
```

---

## Štruktúra projektu

```
spz-register/
├── main.py                  # FastAPI backend (modely, endpointy, auth)
├── frontend/
│   └── index.html           # SPA frontend (JS + Bootstrap)
├── monitoring/
│   ├── compose.yaml         # Prometheus + Grafana stack
│   └── prometheus.yml       # Scrape config
├── scripts/
│   ├── create_admin_inline.py
│   └── backup.sh            # Denná záloha SQLite (cron)
├── Dockerfile
├── compose.yaml
├── requirements.txt
└── data/
    └── db.sqlite
```

---

## Monitoring

Prometheus + Grafana sú nasadené ako samostatný stack (`monitoring/compose.yaml`).
FastAPI vystavuje metriky na `/metrics` (requesty, latency, status kódy per endpoint).

---

## Testovanie

### Funkčné testy (pytest)

```bash
pip install -r tests/requirements.txt
TEST_ADMIN_EMAIL=admin@example.com TEST_ADMIN_PASSWORD=heslo pytest tests/ -v
```

Testy bežia voči produkčnej URL (premenná `TEST_URL`, default: `https://spz.poetika.online`).
Automaticky vytvoria a po teste zmažú testovacieho používateľa `test.auto@spz.test`.

### Záťažové testy (Locust)

**Odporúčané: spustiť z laptopu** (nie zo servera), aby sa predišlo rate-limitingu na `/token`:

```bash
pip install -r tests/requirements.txt
TEST_ADMIN_EMAIL=admin@example.com TEST_ADMIN_PASSWORD=heslo \
  locust -f tests/locustfile.py --host https://spz.poetika.online \
  --headless -u 20 -r 2 --run-time 60s
```

Alebo s web UI na `http://localhost:8089`:
```bash
locust -f tests/locustfile.py --host https://spz.poetika.online
```

**Spúšťanie zo servera:** Locust a app bežia na rovnakej IP, čo spôsobuje
rate-limiting prihlásenia (5/min). Riešenie — dočasne zvýšiť limit v Coolify:
```
RATE_LIMIT_LOGIN=100/minute
```
Po skončení testu vrátiť na `5/minute` a redeployovať.

Locust automaticky vytvorí pool dočasných účtov (`locust-*@spz.test`) a po skončení
testu ich zmaže. Ak cleanup zlyhá, účty možno zmazať ručne cez admin panel.

---

## Licencia

Interný projekt pre potreby mesta Banská Bystrica a partnerských subjektov.
