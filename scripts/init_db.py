import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import engine
from sqlmodel import SQLModel

SQLModel.metadata.create_all(engine)
print("✅ Databáza inicializovaná.")
