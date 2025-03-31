import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlmodel import SQLModel, Field, create_engine, Session, select

SQLModel.metadata.create_all(engine)
print("✅ Databáza inicializovaná.")
