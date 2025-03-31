from sqlmodel import SQLModel, Field, create_engine, Session, select
from passlib.context import CryptContext
import sys
import os

# Inicializácia databázy
sqlite_file_name = "data/db.sqlite"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=False)

# Hashovanie hesiel
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def get_password_hash(password):
    return pwd_context.hash(password)

# User model
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str
    hashed_password: str
    is_admin: bool = False

# Vytvorenie admina
if len(sys.argv) != 3:
    print("Použitie: create_admin_inline.py email heslo")
    sys.exit(1)

email = sys.argv[1]
password = sys.argv[2]

SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        print("Užívateľ už existuje.")
    else:
        new_user = User(email=email, hashed_password=get_password_hash(password), is_admin=True)
        session.add(new_user)
        session.commit()
        print("Admin vytvorený.")
