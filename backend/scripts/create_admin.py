# scripts/create_admin.py
"""
Crée le tout premier compte ADMIN. À lancer une seule fois, manuellement.
Usage : python scripts/create_admin.py
"""
import asyncio
import getpass

from app.db.session import AsyncSessionLocal
from app.core.security import hash_password
from app.db.models.users import User


async def main():
    email = input("Email admin : ")
    name = input("Nom : ")
    password = getpass.getpass("Mot de passe : ")

    async with AsyncSessionLocal() as db:
        admin = User(
        organization_id=None,
        name=name,
        email=email,
        password=hash_password(password),
        role="ADMIN",
        is_active=True,
)
        db.add(admin)
        await db.commit()
        print(f"Admin créé : {email}")


if __name__ == "__main__":
    asyncio.run(main())