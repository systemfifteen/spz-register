import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlmodel import SQLModel, create_engine

sqlite_url = "sqlite:///data/db.sqlite"
engine = create_engine(sqlite_url, echo=False)

SQLModel.metadata.create_all(engine)
print("✅ Databáza inicializovaná.")
