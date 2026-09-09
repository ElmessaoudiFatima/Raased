import argparse
import asyncio
import getpass
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import select
from app.core.security import hash_password
from app.db.models.users import User
from app.db.session import AsyncSessionLocal


async def create_or_update_admin(email: str, first_name: str, last_name: str, password: str):
    email = email.strip().lower()
    first_name = first_name.strip()
    last_name = last_name.strip()

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()

        if user:
            print(f'\n[INFO] Un compte avec l email {email} existe deja (Role: {user.role}).')
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.password = hash_password(password)
            user.role = 'ADMIN'
            user.organization_id = None
            user.email_verified = True
            user.account_status = 'ACTIVE'
            user.is_active = True
            await db.commit()
            print(f'[OK] Le compte {email} a ete mis a jour avec le role ADMIN.')
            return

        admin = User(
            organization_id=None,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=hash_password(password),
            role='ADMIN',
            email_verified=True,
            account_status='ACTIVE',
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print(f'\n[OK] Compte ADMIN cree avec succes : {email}')


def parse_args():
    parser = argparse.ArgumentParser(description='Creer un compte administrateur Raased.')
    parser.add_argument('--email', type=str, help='Email de l administrateur')
    parser.add_argument('--first-name', type=str, default='Admin', help='Prenom')
    parser.add_argument('--last-name', type=str, default='Raased', help='Nom')
    parser.add_argument('--password', type=str, help='Mot de passe')
    return parser.parse_args()


async def main():
    args = parse_args()

    email = args.email
    if not email:
        email = input('Email admin : ').strip()

    first_name = args.first_name
    last_name = args.last_name
    if not args.email:
        fn = input(f'Prenom [{first_name}] : ').strip()
        if fn:
            first_name = fn
        ln = input(f'Nom [{last_name}] : ').strip()
        if ln:
            last_name = ln

    password = args.password
    if not password:
        password = getpass.getpass('Mot de passe : ').strip()

    if not email or not password:
        print('[ERREUR] L email et le mot de passe sont obligatoires.')
        sys.exit(1)

    await create_or_update_admin(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
    )


if __name__ == '__main__':
    asyncio.run(main())
