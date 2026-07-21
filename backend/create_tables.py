import os
import sys

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import engine, SessionLocal
from app.database.base import Base
import app.database.models  # Registers all models
from app.database.models.user import User
from app.core.security import hash_password

def init_db():
    print("Dropping existing tables to migrate user model schema...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("[OK] Old tables dropped.")
    except Exception as e:
        print(f"Warning during drop_all: {e}")

    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created successfully!")

    print("Seeding database with default enterprise users...")
    db = SessionLocal()
    try:
        # Predefined demo accounts
        users_to_seed = [
            {
                "username": "employee",
                "email": "employee@bridgestone.com",
                "role": "EMPLOYEE",
                "password": "employeepassword"
            },
            {
                "username": "manager",
                "email": "manager@bridgestone.com",
                "role": "MANAGER",
                "password": "managerpassword"
            },
            {
                "username": "admin",
                "email": "admin@bridgestone.com",
                "role": "ADMIN",
                "password": "adminpassword"
            }
        ]

        for u_data in users_to_seed:
            existing = db.query(User).filter(User.username == u_data["username"]).first()
            if not existing:
                hashed = hash_password(u_data["password"])
                user = User(
                    username=u_data["username"],
                    email=u_data["email"],
                    role=u_data["role"],
                    hashed_password=hashed,
                    is_active=True
                )
                db.add(user)
                print(f"Seeded user: {u_data['username']} ({u_data['role']})")
        # Seeding completed
            
        db.commit()
        print("[OK] Database seeded successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
