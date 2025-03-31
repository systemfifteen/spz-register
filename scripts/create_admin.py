# scripts/create_admin.py

from sqlalchemy.orm import Session
from app.database import engine, User, get_password_hash
#from database import engine, User, get_password_hash

def create_admin(email: str, password: str):
    db = Session(bind=engine)

    user = db.query(User).filter_by(email=email).first()
    if user:
        print("Používateľ už existuje.")
        return

    new_user = User(email=email, hashed_password=get_password_hash(password))
    db.add(new_user)
    db.commit()
    print("Admin vytvorený:", email)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Použitie: python scripts/create_admin.py <email> <heslo>")
    else:
        create_admin(sys.argv[1], sys.argv[2])
