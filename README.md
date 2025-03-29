# Registrácia ŠPZ – Pešia zóna Banská Bystrica

🅿️ Jednoduchá webová aplikácia na správu vstupov vozidiel do pešej zóny mesta Banská Bystrica. Umožňuje registráciu ŠPZ, správu oprávnení a administráciu vstupov.

## 🔧 Funkcie

- Registrácia a prihlásenie používateľov
- Admin rozhranie na správu používateľov, vozidiel a povolení
- Vyhľadávanie, export do CSV, import nových používateľov
- Možnosť zmeny hesla, hromadného mazania a pridávania vozidiel
- Jednoduchý deployment pomocou Docker Compose

## 🚀 Spustenie (lokálne)

> Vyžaduje [Docker](https://docs.docker.com/get-docker/) a [Docker Compose](https://docs.docker.com/compose/)

```bash
git clone git@github.com:systemfifteen/spz-register.git
cd spz-register
docker-compose build
docker-compose up -d
Aplikácia bude dostupná na http://localhost:8000

Frontend (index.html) môžeš otvoriť cez:

```bash
Copy
Edit
cd frontend
python3 -m http.server 3000
Potom navštív: http://localhost:3000

🔑 Predvolený admin
Po prvom spustení je potrebné ručne zaregistrovať admina cez API alebo frontend, a potom mu ručne nastaviť is_admin = true v databáze (alebo cez rozhranie, ak už je k dispozícii).

📁 Struktúra projektu
bash
Copy
Edit
spz-register/
├── main.py              # FastAPI backend
├── frontend/index.html  # Webové rozhranie
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── db.sqlite            # (voliteľne mountnutý volume)
🧪 Testovanie
Backend podporuje jednoduché curl volania napr.:

bash
Copy
Edit
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@admin.online", "password": "tajneheslo"}'
📦 Import a export
CSV export: kliknutím v admin rozhraní

CSV import: plánované rozšírenie alebo pripravené cez frontend skript

📌 TODO
 Autentifikácia cez OAuth/SSO (napr. mestský systém)

 Validácia formátu ŠPZ

 Logovanie vstupov

 Automatizované zálohy databázy

 Mobilné rozhranie

🧠 Licencia
Vnútorný projekt – určený pre potreby mesta Banská Bystrica alebo partnerských subjektov.

yaml
Copy
Edit

---
