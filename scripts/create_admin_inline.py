import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlmodel import Session, select
from database import engine, User, get_password_hash

if len(sys.argv) != 3:
    print("Použitie: create_admin_inline.py email heslo")
    sys.exit(1)

email = sys.argv[1]
password = sys.argv[2]

with Session(engine) as session:
    result = session.exec(select(User).where(User.email == email)).first()
    if result:
        print("⚠️  Používateľ už existuje.")
    else:
        user = User(email=email, hashed_password=get_password_hash(password), is_admin=True)
        session.add(user)
        session.commit()
        print("✅ Admin vytvorený.")
