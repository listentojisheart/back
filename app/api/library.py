"""
Library read routes for Hu cards and journal fingerprints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models import HuCard, JournalFingerprint
from app.schemas.schemas import (
    HuCardPublic, HuCardDetail,
    JournalFingerprintPublic, JournalFingerprintDetail,
    LibraryStatus,
)
from app.core.deps import get_current_user


router = APIRouter(prefix="/library", tags=["library"])


@router.get("/status", response_model=LibraryStatus)
def library_status(db: Session = Depends(get_db), _=Depends(get_current_user)):
    hu_count = db.query(func.count(HuCard.id)).scalar() or 0

    fingerprints = db.query(JournalFingerprint).all()
    committed = sum(1 for f in fingerprints if f.maturity_tier in ("COMMITTED", "ROBUST"))

    branch_a = {
        "cards_count": hu_count,
        "minimum_viable_threshold": 5,
        "robust_threshold": 12,
        "viable": hu_count >= 5,
        "architecture_version": "v1.5",
    }

    branch_b = {
        "fingerprints": [
            {
                "journal_id": f.journal_id,
                "cards_count": f.cards_count,
                "min_threshold": f.min_threshold,
                "tier": f.maturity_tier,
                "authorization": f.branch_b_authorization,
            }
            for f in fingerprints
        ],
        "total_fingerprints": len(fingerprints),
        "committed_fingerprints": committed,
    }

    return LibraryStatus(
        branch_a=branch_a,
        branch_b=branch_b,
        total_hu_cards=hu_count,
        total_journal_fingerprints=len(fingerprints),
        committed_fingerprints=committed,
    )


@router.get("/hu-cards", response_model=list[HuCardPublic])
def list_hu_cards(db: Session = Depends(get_db), _=Depends(get_current_user)):
    cards = db.query(HuCard).order_by(HuCard.year.desc()).all()
    return [HuCardPublic.model_validate(c) for c in cards]


@router.get("/hu-cards/{paper_id}", response_model=HuCardDetail)
def get_hu_card(paper_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    card = db.query(HuCard).filter(HuCard.paper_id == paper_id).first()
    if not card:
        raise HTTPException(404, "Card not found")
    return HuCardDetail.model_validate(card)


@router.get("/fingerprints", response_model=list[JournalFingerprintPublic])
def list_fingerprints(db: Session = Depends(get_db), _=Depends(get_current_user)):
    fs = db.query(JournalFingerprint).all()
    return [JournalFingerprintPublic.model_validate(f) for f in fs]


@router.get("/fingerprints/{journal_id}", response_model=JournalFingerprintDetail)
def get_fingerprint(journal_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    f = db.query(JournalFingerprint).filter(JournalFingerprint.journal_id == journal_id).first()
    if not f:
        raise HTTPException(404, "Fingerprint not found")
    return JournalFingerprintDetail.model_validate(f)
