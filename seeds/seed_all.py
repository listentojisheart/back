"""
Seed the database with the 5 Hu cards and journal fingerprints from v1.5.

Usage:
    python -m seeds.seed_all

This script is idempotent: re-running updates existing rows rather than duplicating.
"""
import os
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models import HuCard, JournalFingerprint


# ---------- 5 Hu cards (YAML content embedded) ----------
# For brevity, we load from the /seeds/cards directory if present; otherwise use minimal stubs.

CARDS_DIR = Path(__file__).parent / "cards"
FINGERPRINTS_DIR = Path(__file__).parent / "fingerprints"


def _load_card_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def seed_hu_cards():
    db = SessionLocal()
    try:
        if not CARDS_DIR.exists():
            print(f"⚠ {CARDS_DIR} not found — skipping Hu card seeding")
            return

        files = sorted(CARDS_DIR.glob("*.yaml"))
        if not files:
            print(f"⚠ No YAML cards found in {CARDS_DIR}")
            return

        for f in files:
            try:
                data = _load_card_yaml(f)
                paper_id = data.get("paper_id")
                if not paper_id:
                    print(f"  ✗ Skipping {f.name}: no paper_id")
                    continue

                diag = data.get("diagnosis_card", {})
                authors_list = diag.get("authors", [])
                authors = ", ".join(authors_list) if isinstance(authors_list, list) else str(authors_list)
                red_audit = data.get("red_line_audit", {})
                gold_count = 0
                if isinstance(red_audit, dict):
                    summary = red_audit.get("summary", "")
                    if "GOLD" in str(summary):
                        import re
                        m = re.search(r"(\d+)\s*GOLD", str(summary))
                        if m:
                            gold_count = int(m.group(1))

                full_yaml = f.read_text(encoding="utf-8")

                existing = db.query(HuCard).filter(HuCard.paper_id == paper_id).first()
                if existing:
                    existing.title = str(diag.get("title", ""))[:512]
                    existing.authors = authors[:2000]
                    existing.journal = str(diag.get("journal", ""))[:128]
                    existing.year = int(diag.get("year", 2020))
                    existing.author_position = str(diag.get("author_position", ""))[:64]
                    existing.method_path = str(diag.get("method_path", ""))[:64]
                    existing.opening_style = str(diag.get("opening_style", ""))[:64]
                    existing.publisher_era = str(diag.get("publisher_era", ""))[:64] if diag.get("publisher_era") else None
                    existing.red_line_gold_count = gold_count
                    existing.full_yaml = full_yaml
                    existing.card_data = data
                    print(f"  ↻ Updated: {paper_id}")
                else:
                    card = HuCard(
                        paper_id=paper_id,
                        title=str(diag.get("title", ""))[:512],
                        authors=authors[:2000],
                        journal=str(diag.get("journal", ""))[:128],
                        year=int(diag.get("year", 2020)),
                        author_position=str(diag.get("author_position", ""))[:64],
                        method_path=str(diag.get("method_path", ""))[:64],
                        opening_style=str(diag.get("opening_style", ""))[:64],
                        publisher_era=str(diag.get("publisher_era", ""))[:64] if diag.get("publisher_era") else None,
                        red_line_gold_count=gold_count,
                        full_yaml=full_yaml,
                        card_data=data,
                        extractor_version="v1.5",
                    )
                    db.add(card)
                    print(f"  ✓ Added: {paper_id}")
            except Exception as e:
                print(f"  ✗ Failed {f.name}: {e}")

        db.commit()
        print(f"✓ Hu card seeding complete ({len(files)} files processed)")
    finally:
        db.close()


def seed_fingerprints():
    db = SessionLocal()
    try:
        # POM-SAGE CANDIDATE (committed sub-features)
        pom_sage_data = {
            "journal_id": "POM_SAGE",
            "full_name": "Production and Operations Management (SAGE era, post-2024)",
            "publisher_era": "POM-SAGE",
            "maturity_tier": "CANDIDATE",
            "cards_count": 2,
            "min_threshold": 6,
            "branch_b_authorization": "gap_audit_only",
            "features": {
                "abstract_format": "single paragraph, 7-10 micro-moves",
                "section_mergers": "1 typical",
                "standalone_section_6": "Implications or Counterfactual with audience/strategy subsections",
                "title_pattern": "colon + suffix structure",
                "intro_paragraphs": "8-9",
            },
        }
        _upsert_fingerprint(db, pom_sage_data, committed=True)

        # Seeds (n=1 each)
        msom_data = {
            "journal_id": "MSOM",
            "full_name": "Manufacturing & Service Operations Management",
            "publisher_era": "INFORMS",
            "maturity_tier": "SEED",
            "cards_count": 1,
            "min_threshold": 6,
            "branch_b_authorization": "denied",
            "features": {
                "abstract_format": "5-segment structured",
                "section_mergers": "0",
                "intro_paragraphs": "7",
                "title_pattern": "gerund + colon + tension pair",
            },
        }
        _upsert_fingerprint(db, msom_data)

        pom_wiley_data = {
            "journal_id": "POM_Wiley",
            "full_name": "Production and Operations Management (Wiley era, pre-2024)",
            "publisher_era": "POM-Wiley",
            "maturity_tier": "SEED",
            "cards_count": 1,
            "min_threshold": 6,
            "branch_b_authorization": "denied",
            "features": {
                "abstract_format": "single paragraph",
                "section_mergers": "2",
                "intro_paragraphs": "10",
                "title_pattern": "Effect of X on Y (no colon)",
            },
        }
        _upsert_fingerprint(db, pom_wiley_data)

        ms_data = {
            "journal_id": "MS",
            "full_name": "Management Science",
            "publisher_era": "INFORMS",
            "maturity_tier": "SEED",
            "cards_count": 1,
            "min_threshold": 6,
            "branch_b_authorization": "denied",
            "features": {
                "abstract_format": "single paragraph",
                "section_mergers": "2",
                "intro_paragraphs": "10",
                "title_pattern": "Concept with Y: An Empirical Analysis of Z",
            },
        }
        _upsert_fingerprint(db, ms_data)

        db.commit()
        print("✓ Journal fingerprints seeded")
    finally:
        db.close()


def _upsert_fingerprint(db, data: dict, committed: bool = False):
    journal_id = data["journal_id"]
    yaml_body = yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    existing = db.query(JournalFingerprint).filter(JournalFingerprint.journal_id == journal_id).first()
    if existing:
        existing.full_name = data["full_name"]
        existing.publisher_era = data.get("publisher_era")
        existing.maturity_tier = data["maturity_tier"]
        existing.cards_count = data["cards_count"]
        existing.min_threshold = data["min_threshold"]
        existing.branch_b_authorization = data["branch_b_authorization"]
        existing.fingerprint_yaml = yaml_body
        existing.fingerprint_data = data
        if committed and not existing.committed_at:
            existing.committed_at = datetime.now(timezone.utc)
        print(f"  ↻ Updated fingerprint: {journal_id}")
    else:
        fp = JournalFingerprint(
            journal_id=journal_id,
            full_name=data["full_name"],
            publisher_era=data.get("publisher_era"),
            maturity_tier=data["maturity_tier"],
            cards_count=data["cards_count"],
            min_threshold=data["min_threshold"],
            branch_b_authorization=data["branch_b_authorization"],
            fingerprint_yaml=yaml_body,
            fingerprint_data=data,
            committed_at=datetime.now(timezone.utc) if committed else None,
        )
        db.add(fp)
        print(f"  ✓ Added fingerprint: {journal_id}")


if __name__ == "__main__":
    print("=" * 60)
    print("TK-7 Library Seeding")
    print("=" * 60)
    seed_hu_cards()
    print()
    seed_fingerprints()
    print()
    print("✓ All seeding complete")
