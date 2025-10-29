# scripts/create_admin_inline.py

from sqlmodel import SQLModel, Field, create_engine, Session, select
from passlib.context import CryptContext
from typing import Optional
from uuid import uuid4
import sys
import os
import bcrypt
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("obj", (), {"__version__": bcrypt.__version__})

# Heslo hashovanie
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Model používateľa (rovnaký ako v main.py)
class User(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str
    hashed_password: str
    is_admin: bool = False

# Nastavenie databázy
sqlite_file_name = "data/db.sqlite"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=False)

# Inicializácia DB (ak netreba, nevadí)
SQLModel.metadata.create_all(engine)

# Čítanie argumentov
if len(sys.argv) != 3:
    print("Použitie: python3 scripts/create_admin_inline.py <email> <heslo>")
    sys.exit(1)

email = sys.argv[1]
password = sys.argv[2]

with Session(engine) as session:
    existing_user = session.exec(select(User).where(User.email == email)).first()

    if existing_user:
        print(f"⚠️ Používateľ {email} už existuje.")
    else:
        new_user = User(
            email=email,
            hashed_password=get_password_hash(password),
            is_admin=True
        )
        session.add(new_user)
        session.commit()
        print(f"✅ Admin používateľ {email} bol vytvorený.")