import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from database import Base, engine, User, get_password_hash
import sys

if len(sys.argv) != 3:
    print("Použitie: create_admin_inline.py email heslo")
    sys.exit(1)

email = sys.argv[1]
password = sys.argv[2]

db = Session(bind=engine)
existing = db.query(User).filter_by(email=email).first()
if existing:
    print("⚠️  Používateľ už existuje.")
else:
    new_user = User(email=email, hashed_password=get_password_hash(password), is_admin=True)
    db.add(new_user)
    db.commit()
    print("✅ Admin vytvorený.")
