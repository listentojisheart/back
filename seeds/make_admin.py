"""
Promote a user to admin by email or username.

Usage:
    python -m seeds.make_admin --email hu@oxford.edu
    python -m seeds.make_admin --username you
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import or_
from app.db.session import SessionLocal
from app.models import User


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--email", type=str)
    p.add_argument("--username", type=str)
    args = p.parse_args()

    if not args.email and not args.username:
        print("Must provide --email or --username")
        sys.exit(1)

    db = SessionLocal()
    try:
        q = db.query(User)
        if args.email:
            user = q.filter(User.email == args.email).first()
        else:
            user = q.filter(User.username == args.username).first()
        if not user:
            print("User not found")
            sys.exit(1)
        user.is_admin = True
        db.commit()
        print(f"✓ Promoted {user.username} ({user.email}) to admin")
    finally:
        db.close()


if __name__ == "__main__":
    main()
