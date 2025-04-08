# scripts/migrate_add_login_fields.py
import sqlite3

db_path = "data/db.sqlite"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE user ADD COLUMN login_count INTEGER DEFAULT 0")
    print("✅ Pridaný stĺpec 'login_count'")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("ℹ️ Stĺpec 'login_count' už existuje.")
    else:
        raise

try:
    cursor.execute("ALTER TABLE user ADD COLUMN last_login TEXT")
    print("✅ Pridaný stĺpec 'last_login'")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("ℹ️ Stĺpec 'last_login' už existuje.")
    else:
        raise

conn.commit()
conn.close()
