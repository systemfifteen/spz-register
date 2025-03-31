import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from database import Base, User, get_password_hash

if len(sys.argv) < 3:
    print("Použitie: create_admin_inline.py <email> <heslo>")
    sys.exit(1)

email = sys.argv[1]
password = sys.argv[2]

# Absolútna cesta k databáze
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'data', 'db.sqlite')
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

Base.metadata.create_all(engine)
db = Session(bind=engine)

existing = db.query(User).filter_by(email=email).first()
if not existing:
    new_user = User(email=email, hashed_password=get_password_hash(password), is_admin=True)
    db.add(new_user)
    db.commit()
    print("Admin vytvorený.")
else:
    print("Používateľ už existuje.")
