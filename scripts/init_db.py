import os
from sqlalchemy import create_engine
from database import Base

# Absolútna cesta k databáze vo vnútri kontajnera
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'data', 'db.sqlite')
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

Base.metadata.create_all(engine)
print("Databáza inicializovaná.")
