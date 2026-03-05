import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Body, Request, Response, Cookie
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from passlib.context import CryptContext
from sqlmodel import SQLModel, Field, Session, create_engine, select, delete
from typing import List, Optional
from uuid import uuid4
from io import StringIO
from datetime import datetime, timedelta
from jose import JWTError, jwt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
import csv
import re
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://spz.poetika.online").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, include_in_schema=False)

sqlite_file_name = "data/db.sqlite"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=False)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

if SECRET_KEY == "change-me-in-production":
    raise RuntimeError("SECRET_KEY nie je nastavený! Nastav ho cez environment premennú.")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM") or SMTP_USER

def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

class User(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str = Field(unique=True)
    hashed_password: str
    is_admin: bool = False
    login_count: int = 0
    last_login: Optional[datetime] = None

class UserPublic(BaseModel):
    id: str
    email: str
    is_admin: bool
    login_count: int
    last_login: Optional[datetime]

class UserWithPermission(UserPublic):
    daily_entries: Optional[int] = None
    time_window: Optional[str] = None

class UserCreate(BaseModel):
    email: str
    password: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('Neplatný formát emailu')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Heslo musí mať aspoň 8 znakov')
        return v

class Vehicle(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str
    spz: str

class VehicleCreate(BaseModel):
    spz: str

    @field_validator('spz')
    @classmethod
    def validate_spz(cls, v: str) -> str:
        v = v.upper().strip().replace(' ', '').replace('-', '')
        if not re.match(r'^[A-Z]{2}\d{3}[A-Z]{2}$', v):
            raise ValueError('Neplatný formát ŠPZ (očakávaný formát: BA123AB)')
        return v

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

class PasswordResetToken(SQLModel, table=True):
    token: str = Field(primary_key=True)
    user_id: str
    expires_at: datetime

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

def get_user_by_token(
    access_token: Optional[str] = Cookie(default=None),
    bearer_token: Optional[str] = Depends(oauth2_scheme),
) -> User:
    token = access_token or bearer_token
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

def require_admin(user: User = Depends(get_user_by_token)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    return user

@app.post("/register")
@limiter.limit("5/minute")
def register(request: Request, user: UserCreate):
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
@limiter.limit("5/minute")
def login(request: Request, response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == form_data.username)).first()
        if not user or not pwd_context.verify(form_data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect email or password")

        # 🆕 aktualizuj počet prihlásení a čas
        user.login_count += 1
        user.last_login = datetime.now()
        session.add(user)
        session.commit()

        token = create_access_token(user.id)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        )
        return {"message": "Prihlásenie úspešné"}

@app.get("/me", response_model=UserPublic)
def get_me(user: User = Depends(get_user_by_token)):
    return user

@app.post("/logout")
def logout(response: Response, user: User = Depends(get_user_by_token)):
    response.delete_cookie("access_token")
    return {"message": "Odhlásenie úspešné"}

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
def list_all_vehicles(user: User = Depends(require_admin)):
    with Session(engine) as session:
        return session.exec(select(Vehicle)).all()

@app.post("/admin/permissions/{user_id}")
def set_permission(user_id: str, data: PermissionUpdate, user: User = Depends(require_admin)):
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
def get_permission_for_user(user_id: str, user: User = Depends(require_admin)):
    with Session(engine) as session:
        perm = session.get(Permission, user_id)
        if not perm:
            raise HTTPException(status_code=404, detail="Permission not set")
        return perm

@app.get("/admin/users", response_model=List[UserWithPermission])
def list_users(user: User = Depends(require_admin)):
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        permissions = {p.user_id: p for p in session.exec(select(Permission)).all()}
        return [
            UserWithPermission(**u.model_dump(), **({
                "daily_entries": p.daily_entries,
                "time_window": p.time_window,
            } if (p := permissions.get(u.id)) else {}))
            for u in users
        ]

@app.post("/admin/vehicles/{user_id}")
def add_vehicle_admin(user_id: str, vehicle: VehicleCreate, user: User = Depends(require_admin)):
    with Session(engine) as session:
        new_vehicle = Vehicle(user_id=user_id, spz=vehicle.spz)
        session.add(new_vehicle)
        session.commit()
        return new_vehicle

@app.get("/admin/export")
def export_csv(user: User = Depends(require_admin)):

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
def admin_create_user(data: UserCreate, is_admin: Optional[bool] = False, user: User = Depends(require_admin)):

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
def delete_users(user_ids: List[str] = Body(...), user: User = Depends(require_admin)):
    
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
    user: User = Depends(require_admin)
):

    created = []
    invalid = []
    with Session(engine) as session:
        for row in data:
            if not row or row[0].startswith('#'):
                continue
            if len(row) < 2:
                continue
            email = row[0].strip().lower()
            password = row[1].strip()
            is_admin = row[2].strip().lower() == "true" if len(row) > 2 else False

            if '@' not in email or '.' not in email.split('@')[-1]:
                invalid.append(email)
                continue
            if len(password) < 8:
                invalid.append(email)
                continue

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
    return {"message": f"Importovaných {len(created)} používateľov", "invalid": invalid}

def send_reset_email(to_email: str, token: str):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        raise HTTPException(status_code=503, detail="Email nie je nakonfigurovaný")
    reset_url = f"{ALLOWED_ORIGINS[0]}/?token={token}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset hesla – SPZ Register"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    text = f"Odkaz na reset hesla:\n{reset_url}\n\nOdkaz je platný 1 hodinu."
    html = (
        f"<p>Požiadali ste o reset hesla.</p>"
        f'<p><a href="{reset_url}">Kliknite sem pre reset hesla</a></p>'
        f"<p>Alebo skopírujte odkaz: {reset_url}</p>"
        f"<p><small>Odkaz je platný 1 hodinu. "
        f"Ak ste o reset nepožiadali, ignorujte tento email.</small></p>"
    )
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())


@app.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(request: Request, data: PasswordResetRequest):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == data.email.strip().lower())).first()
        if user:
            session.exec(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
            token = secrets.token_urlsafe(32)
            reset_token = PasswordResetToken(
                token=token,
                user_id=user.id,
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            session.add(reset_token)
            session.commit()
            try:
                send_reset_email(user.email, token)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=503, detail="Nepodarilo sa odoslať email")
    return {"message": "Ak email existuje, bol odoslaný odkaz na reset hesla"}


@app.post("/reset-password")
def reset_password(data: PasswordResetConfirm):
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Heslo musí mať aspoň 8 znakov")
    with Session(engine) as session:
        reset_token = session.get(PasswordResetToken, data.token)
        if not reset_token:
            raise HTTPException(status_code=400, detail="Neplatný alebo expirovaný token")
        if reset_token.expires_at < datetime.utcnow():
            session.delete(reset_token)
            session.commit()
            raise HTTPException(status_code=400, detail="Token expiroval")
        user = session.get(User, reset_token.user_id)
        if not user:
            session.delete(reset_token)
            session.commit()
            raise HTTPException(status_code=400, detail="Používateľ neexistuje")
        user.hashed_password = pwd_context.hash(data.new_password)
        session.add(user)
        session.delete(reset_token)
        session.commit()
    return {"message": "Heslo bolo úspešne zmenené"}


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

#servujeme staticky frontend cez fastapi
if os.path.isdir("frontend"):
    app.mount("/static", StaticFiles(directory="frontend", html=True), name="static")

@app.get("/")
def read_index():
    return FileResponse("frontend/index.html")