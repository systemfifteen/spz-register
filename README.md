# 🅿️ Registrácia ŠPZ – Pešia zóna Banská Bystrica

Jednoduchá webová aplikácia na správu vstupov vozidiel do pešej zóny mesta Banská Bystrica. Umožňuje registráciu ŠPZ, správu oprávnení a administráciu vstupov.

---

## ✨ Funkcie

- Registrácia a prihlásenie používateľov
- Admin rozhranie na správu používateľov, vozidiel a povolení
- Vyhľadávanie, export do CSV, import nových používateľov
- Možnosť zmeny hesla, hromadného mazania a pridávania vozidiel
- Frontend servovaný z backendu (1 Docker kontajner)
- Nasadenie pomocou Docker Compose

---

## 🚀 Nasadenie na serveri (s Docker Compose)

> Vyžaduje: [Docker](https://docs.docker.com/get-docker/) a [Docker Compose](https://docs.docker.com/compose/)

```bash
git clone https://github.com/systemfifteen/spz-register.git
cd spz-register
docker compose up -d --build
```

Aplikácia bude dostupná na `http://localhost:8000` (alebo cez reverzný proxy na zvolenej doméne).

---

## 🧑‍💻 Pridanie admin používateľa

Ak je databáza prázdna alebo nová, admina pridáš takto:

1. Inicializuj databázu (len raz pri prvej inštalácii):

```bash
docker exec -it fastapi-spz python3 scripts/init_db.py
```

2. Pridaj admina:

```bash
docker exec -it fastapi-spz python3 scripts/create_admin_inline.py admin@poetika.online tajneheslo
```

---

## 🧪 Testovanie API

```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@poetika.online&password=tajneheslo"
```

---

## 📁 Struktúra projektu

```
spz-register/
├── main.py                  # FastAPI backend + frontend serving
├── frontend/                # Webové rozhranie (index.html + JS)
├── scripts/                 # DB inicializácia, vytváranie admina
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── data/db.sqlite           # SQLite databáza (mountovaná)
```

---

## 📦 Import / export

- CSV export: dostupný cez admin rozhranie
- CSV import: zatiaľ manuálne (plánované rozšírenie)

---

## 📌 TODO

- ✅ Nasadenie s reverzným proxy (HAProxy, HTTPS, SNI)
- 🔒 Validácia formátu ŠPZ
- 📊 Logovanie vstupov
- 📤 Automatické zálohy DB
- 📱 Mobilná verzia
- 🔐 OAuth/SSO autentifikácia

---

## 🧠 Licencia

Interný projekt pre potreby mesta Banská Bystrica a partnerských subjektov.