import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Base, engine

Base.metadata.create_all(bind=engine)
print("✅ Databáza inicializovaná.")
