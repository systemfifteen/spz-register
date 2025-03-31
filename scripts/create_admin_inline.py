from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
import sys

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False)

# SQLite path
engine = create_engine("sqlite:///data/db.sqlite", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Získaj údaje z argumentov
if len(sys.argv) != 3:
    print("Použitie: python3 scripts/create_admin_inline.py email heslo")
    sys.exit(1)

email = sys.argv[1]
password = sys.argv[2]

db = SessionLocal()
existing = db.query(User).filter_by(email=email).first()
if existing:
    print("Používateľ už existuje.")
else:
    user = User(email=email, hashed_password=get_password_hash(password), is_admin=True)
    db.add(user)
    db.commit()
    print("Admin vytvorený.")
