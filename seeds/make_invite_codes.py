"""
Generate N invite codes. Prints them to stdout.

Usage:
    python -m seeds.make_invite_codes --count 10 --note "Hu lab batch 1"
"""
import argparse
import secrets
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models import InviteCode


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--note", type=str, default=None)
    p.add_argument("--max-uses", type=int, default=1)
    p.add_argument("--expires-days", type=int, default=None)
    args = p.parse_args()

    db = SessionLocal()
    try:
        expires_at = None
        if args.expires_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=args.expires_days)

        print(f"Generating {args.count} invite codes:")
        print("-" * 50)
        codes = []
        for _ in range(args.count):
            code_str = secrets.token_urlsafe(9)
            invite = InviteCode(
                code=code_str,
                note=args.note,
                max_uses=args.max_uses,
                expires_at=expires_at,
            )
            db.add(invite)
            codes.append(code_str)

        db.commit()

        for c in codes:
            print(f"  {c}")
        print("-" * 50)
        print(f"✓ Created {args.count} codes")
        if args.note:
            print(f"  Note: {args.note}")
        if args.max_uses > 1:
            print(f"  Max uses each: {args.max_uses}")
        if expires_at:
            print(f"  Expires: {expires_at.isoformat()}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
