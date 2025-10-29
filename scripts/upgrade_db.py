# scripts/upgrade_db.py
import sqlite3
import os

db_path = "data/db.sqlite"

if not os.path.exists(db_path):
    print("⚠️ Databáza neexistuje – nič na upgrade.")
    exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Zoznam očakávaných stĺpcov a ich SQL definície
expected_columns = {
    "login_count": "INTEGER DEFAULT 0 NOT NULL",
    "last_login_at": "TEXT"
}

cursor.execute("PRAGMA table_info(user);")
existing_columns = {row[1] for row in cursor.fetchall()}

added = False
for col, definition in expected_columns.items():
    if col not in existing_columns:
        print(f"➕ Pridávam stĺpec: {col}")
        cursor.execute(f"ALTER TABLE user ADD COLUMN {col} {definition};")
        added = True
    else:
        print(f"✅ Stĺpec {col} už existuje.")

if added:
    conn.commit()
    print("🎉 Upgrade databázy úspešný.")
else:
    print("✅ Databáza už bola aktuálna, netreba nič meniť.")

conn.close()
