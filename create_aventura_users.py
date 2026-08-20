import sys
sys.path.append('.')
from backend.db import SessionLocal
from backend.models import User
from backend.main import _hash_password

db = SessionLocal()

users_to_create = [
    {
        "username": "juridicoerozo@gmail.com",
        "email": "juridicoerozo@gmail.com",
        "nombre": "ESTEFANIA ROZO OSORIO",
        "password": "Aventuraestefania2026$%",
        "company_id": 3,
        "role": "usuario_regular"
    },
    {
        "username": "jsarias@motoexperiencia.com",
        "email": "jsarias@motoexperiencia.com",
        "nombre": "SEBASTIAN ARIAS",
        "password": "Aventurasebastian2026$%",
        "company_id": 3,
        "role": "usuario_regular"
    },
    {
        "username": "auxjuridico@motoexperiencia.com",
        "email": "auxjuridico@motoexperiencia.com",
        "nombre": "ANDRES",
        "password": "Aventuraandres2026$%",
        "company_id": 3,
        "role": "usuario_regular"
    }
]

for ud in users_to_create:
    existing = db.query(User).filter(User.username == ud["username"]).first()
    if existing:
        print(f"User {ud['username']} already exists")
    else:
        new_user = User(
            username=ud["username"],
            email=ud["email"],
            nombre=ud["nombre"],
            hashed_password=_hash_password(ud["password"]),
            company_id=ud["company_id"],
            role=ud["role"],
            is_active=True,
            is_admin=False,
            is_superadmin=False
        )
        db.add(new_user)
        print(f"Created user {ud['username']} with password {ud['password']}")

db.commit()
print("Done!")
