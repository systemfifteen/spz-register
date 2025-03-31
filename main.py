from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from passlib.context import CryptContext
from sqlmodel import SQLModel, Field, Session, create_engine, select, delete
from typing import List, Optional
from uuid import uuid4
from io import StringIO
import csv


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sqlite_file_name = "data/db.sqlite"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=False)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
tokens = {}

class User(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str
    hashed_password: str
    is_admin: bool = False

class UserCreate(BaseModel):
    email: str
    password: str

class Vehicle(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str
    spz: str

class VehicleCreate(BaseModel):
    spz: str

class Permission(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    daily_entries: int
    time_window: Optional[str] = "04:00 - 09:00"

class PermissionUpdate(BaseModel):
    daily_entries: int
    time_window: Optional[str] = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

def get_user_by_token(token: str = Depends(oauth2_scheme)) -> User:
    user_id = tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

@app.post("/register")
def register(user: UserCreate):
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == user.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        hashed = pwd_context.hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed)
        session.add(new_user)
        session.commit()
        return {"message": "User registered"}

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == form_data.username)).first()
        if not user or not pwd_context.verify(form_data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        token = str(uuid4())
        tokens[token] = user.id
        return {"access_token": token, "token_type": "bearer"}

@app.get("/me")
def get_me(user: User = Depends(get_user_by_token)):
    return user

@app.post("/vehicles")
def add_vehicle(vehicle: VehicleCreate, user: User = Depends(get_user_by_token)):
    with Session(engine) as session:
        new_vehicle = Vehicle(user_id=user.id, spz=vehicle.spz)
        session.add(new_vehicle)
        session.commit()
        return new_vehicle

@app.get("/vehicles")
def list_vehicles(user: User = Depends(get_user_by_token)):
    with Session(engine) as session:
        return session.exec(select(Vehicle).where(Vehicle.user_id == user.id)).all()

@app.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str, user: User = Depends(get_user_by_token)):
    with Session(engine) as session:
        vehicle = session.get(Vehicle, vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if not user.is_admin and vehicle.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        session.delete(vehicle)
        session.commit()
        return {"message": "Deleted"}

@app.get("/admin/vehicles")
def list_all_vehicles(user: User = Depends(get_user_by_token)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    with Session(engine) as session:
        return session.exec(select(Vehicle)).all()

@app.post("/admin/permissions/{user_id}")
def set_permission(user_id: str, data: PermissionUpdate, user: User = Depends(get_user_by_token)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    with Session(engine) as session:
        perm = session.get(Permission, user_id)
        if perm:
            perm.daily_entries = data.daily_entries
            if data.time_window:
                perm.time_window = data.time_window
        else:
            perm = Permission(user_id=user_id, daily_entries=data.daily_entries, time_window=data.time_window or "04:00 - 09:00")
            session.add(perm)
        session.commit()
        return {"message": "Permission updated"}

@app.get("/permissions")
def get_permission(user: User = Depends(get_user_by_token)):
    with Session(engine) as session:
        perm = session.get(Permission, user.id)
        if not perm:
            raise HTTPException(status_code=404, detail="Permission not set")
        return perm

@app.get("/admin/permissions/{user_id}")
def get_permission_for_user(user_id: str, user: User = Depends(get_user_by_token)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    with Session(engine) as session:
        perm = session.get(Permission, user_id)
        if not perm:
            raise HTTPException(status_code=404, detail="Permission not set")
        return perm

@app.get("/admin/users")
def list_users(user: User = Depends(get_user_by_token)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    with Session(engine) as session:
        return session.exec(select(User)).all()

@app.post("/admin/vehicles/{user_id}")
def add_vehicle_admin(user_id: str, vehicle: VehicleCreate, user: User = Depends(get_user_by_token)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    with Session(engine) as session:
        new_vehicle = Vehicle(user_id=user_id, spz=vehicle.spz)
        session.add(new_vehicle)
        session.commit()
        return new_vehicle

@app.get("/admin/export")
def export_csv(user: User = Depends(get_user_by_token)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "user_id", "is_admin", "daily_entries", "time_window", "spz"])

    with Session(engine) as session:
        users = session.exec(select(User)).all()
        vehicles = session.exec(select(Vehicle)).all()
        permissions = {p.user_id: p for p in session.exec(select(Permission)).all()}

        for u in users:
            user_perm = permissions.get(u.id)
            user_vehicles = [v.spz for v in vehicles if v.user_id == u.id]
            if user_vehicles:
                for spz in user_vehicles:
                    writer.writerow([
                        u.email, u.id, u.is_admin,
                        user_perm.daily_entries if user_perm else "",
                        user_perm.time_window if user_perm else "",
                        spz
                    ])
            else:
                writer.writerow([
                    u.email, u.id, u.is_admin,
                    user_perm.daily_entries if user_perm else "",
                    user_perm.time_window if user_perm else "",
                    ""
                ])

    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=export.csv"
    })

@app.post("/admin/users")
def admin_create_user(data: UserCreate, is_admin: Optional[bool] = False, user: User = Depends(get_user_by_token)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")

    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == data.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
        new_user = User(
            email=data.email,
            hashed_password=pwd_context.hash(data.password),
            is_admin=is_admin
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return {"message": "Používateľ vytvorený", "user_id": new_user.id}

@app.delete("/admin/users")
def delete_users(user_ids: List[str] = Body(...), user: User = Depends(get_user_by_token)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    
    with Session(engine) as session:
        for uid in user_ids:
            session.exec(delete(Vehicle).where(Vehicle.user_id == uid))  # zmaž ŠPZ
            session.exec(delete(Permission).where(Permission.user_id == uid))  # zmaž povolenie
            session.exec(delete(User).where(User.id == uid))  # zmaž používateľa
        session.commit()
    
    return {"message": f"Zmazaných {len(user_ids)} používateľov"}

@app.post("/admin/import")
def import_users(
    data: List[List[str]] = Body(...),
    user: User = Depends(get_user_by_token)
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")

    created = []
    with Session(engine) as session:
        for row in data:
            if len(row) < 2:
                continue
            email, password = row[0].strip(), row[1].strip()
            is_admin = row[2].strip().lower() == "true" if len(row) > 2 else False

            exists = session.exec(select(User).where(User.email == email)).first()
            if exists:
                continue
            new_user = User(
                email=email,
                hashed_password=pwd_context.hash(password),
                is_admin=is_admin
            )
            session.add(new_user)
            created.append(email)
        session.commit()
    return {"message": f"Importovaných {len(created)} používateľov"}

@app.post("/change-password")
def change_password(data: PasswordChange, user: User = Depends(get_user_by_token)):
    with Session(engine) as session:
        db_user = session.get(User, user.id)
        if not db_user or not pwd_context.verify(data.old_password, db_user.hashed_password):
            raise HTTPException(status_code=400, detail="Nesprávne aktuálne heslo")

        db_user.hashed_password = pwd_context.hash(data.new_password)
        session.add(db_user)
        session.commit()

    return {"message": "Heslo bolo zmenené"}

@app.get("/health")
def health():
    return {"status": "ok"}
