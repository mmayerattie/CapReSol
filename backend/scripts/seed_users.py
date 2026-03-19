"""
Seed users from USERS_CONFIG env var.
Run: python -m scripts.seed_users  (from backend/)

USERS_CONFIG format in .env:
USERS_CONFIG=[{"username":"alice","password":"secret1"},{"username":"bob","password":"secret2"}]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db.session import SessionLocal
from app.db.models import User
from app.api.auth import hash_password


def seed():
    if not settings.USERS_CONFIG:
        print("USERS_CONFIG is empty — nothing to seed.")
        return

    db = SessionLocal()
    try:
        created = 0
        for entry in settings.USERS_CONFIG:
            username = entry["username"]
            password = entry["password"]
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                print(f"  skip {username} (already exists)")
                continue
            user = User(username=username, hashed_password=hash_password(password))
            db.add(user)
            created += 1
            print(f"  created {username}")
        db.commit()
        print(f"Done — {created} user(s) created.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
