# scripts/upgrade_db.py
import sqlite3
import os

db_path = "data/db.sqlite"

if not os.path.exists(db_path):
    print("⚠️ Databáza neexistuje – nič na upgrade.")
    exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(user);")
existing_columns = {row[1] for row in cursor.fetchall()}

# Migrácia 1: Pridanie stĺpcov pre sledovanie prihlásení
login_columns = {
    "login_count": "INTEGER DEFAULT 0 NOT NULL",
    "last_login": "TEXT"
}

added = False
for col, definition in login_columns.items():
    if col not in existing_columns:
        print(f"➕ Pridávam stĺpec: {col}")
        cursor.execute(f"ALTER TABLE user ADD COLUMN {col} {definition};")
        added = True
    else:
        print(f"✅ Stĺpec {col} už existuje.")

# Migrácia 2: Unique index na email
cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_user_email';")
if not cursor.fetchone():
    try:
        cursor.execute("CREATE UNIQUE INDEX idx_user_email ON user(email);")
        print("➕ Unique index na email vytvorený.")
        added = True
    except sqlite3.IntegrityError:
        print("⚠️ Unique index sa nedal vytvoriť – v databáze sú duplicitné emaily. Oprav ich ručne.")
else:
    print("✅ Unique index na email už existuje.")

if added:
    conn.commit()
    print("🎉 Upgrade databázy úspešný.")
else:
    print("✅ Databáza už bola aktuálna, netreba nič meniť.")

conn.close()
