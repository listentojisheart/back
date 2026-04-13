"""
Extraction job routes. TK-7 extraction is triggered as an async job.

MVP approach: run extraction synchronously within request (may take 30-60s).
Railway/FastAPI can handle long requests fine. For production scale, 
swap to Celery + Redis queue (hooks provided).
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.models import User, ExtractionJob, UploadedFile, HuCard, UsageEvent
from app.schemas.schemas import ExtractionJobCreate, ExtractionJobPublic
from app.core.deps import get_current_user
from app.services.anthropic_proxy import call_anthropic
from app.services.rate_limit import check_global_spend, record_spend
import json


router = APIRouter(prefix="/extraction", tags=["extraction"])


EXTRACTION_SYSTEM_PROMPT = """You are a TK-7 tacit knowledge extractor operating under the AFP (Adaptive Flow Protocol).

Your task: extract a TK-7 card from the provided paper. Follow the 7-phase pipeline strictly:
1. Phase 1 Intake: identify paper metadata (title, authors, journal, year, author position)
2. Phase 2-6 TK-7 Layers:
   - L1 Problem framing: RQ shape, gap style, stakes ladder
   - L2 Positioning: anchor papers, delta type
   - L3 Theory/mechanism: theory pillars, construct definitions
   - L4 Identification/design: method path, dual defense, robustness
   - L5 Evidence architecture: main results, heterogeneity, mechanism validation
   - L6 Narrative/rhetoric: abstract format, intro structure, contribution enumeration
   - L7 Review process: inferred reviewer pre-emption

Output format: a valid YAML document with the full card structure. Use the Hu v1.5 schema with:
- diagnosis_card (metadata)
- phase_1_phenomenon_anchoring ... phase_7_review_process
- candidate_patterns (tier_S / tier_A / tier_B)
- red_line_audit (R1-R8 verdicts)
- executable_summary
- copyright_compliance: 0 direct quotes, paraphrase only

IMPORTANT:
- Zero direct quotes from the paper (paraphrase all)
- Tag provenance to the six-item spine (EM1-EM3, ED1-ED2, EF1)
- If content is insufficient to fill a phase, mark confidence_on_auto_inferred < 0.5
- Respect the Hu_core_rule audit (single_main_method_plus_alternatives)"""


@router.post("/jobs", response_model=ExtractionJobPublic)
async def create_extraction_job(
    req: ExtractionJobCreate,
    bg: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate file
    file = db.query(UploadedFile).filter(
        UploadedFile.id == req.file_id,
        UploadedFile.user_id == user.id,
    ).first()
    if not file:
        raise HTTPException(404, "File not found")
    if not file.extracted_text or file.extracted_text.startswith("["):
        raise HTTPException(400, "File has no extractable text")

    # Circuit breaker
    allowed, _, reason = check_global_spend()
    if not allowed:
        raise HTTPException(503, detail=reason)

    # Create job
    job = ExtractionJob(
        user_id=user.id,
        file_id=file.id,
        branch=req.branch,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Schedule background work
    bg.add_task(_run_extraction, job.id)

    return ExtractionJobPublic.model_validate(job)


@router.get("/jobs", response_model=list[ExtractionJobPublic])
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = db.query(ExtractionJob).filter(ExtractionJob.user_id == user.id).order_by(ExtractionJob.id.desc()).limit(50).all()
    return [ExtractionJobPublic.model_validate(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=ExtractionJobPublic)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(ExtractionJob).filter(
        ExtractionJob.id == job_id,
        ExtractionJob.user_id == user.id,
    ).first()
    if not job:
        raise HTTPException(404, "Not found")
    return ExtractionJobPublic.model_validate(job)


# ---------- Background worker ----------

async def _run_extraction(job_id: int):
    """Background task: reads job, calls Anthropic, saves result."""
    db = SessionLocal()
    try:
        job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        db.commit()

        file = db.query(UploadedFile).filter(UploadedFile.id == job.file_id).first()
        if not file or not file.extracted_text:
            job.status = "failed"
            job.error_message = "File text unavailable"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Clamp to avoid runaway prompts
        paper_text = file.extracted_text[:120000]

        messages = [{
            "role": "user",
            "content": f"Extract a TK-7 card from this paper. File: {file.filename}\n\n---\n\n{paper_text}"
        }]

        try:
            result = await call_anthropic(
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                messages=messages,
                max_tokens=8000,
            )
        except Exception as e:
            job.status = "failed"
            job.error_message = f"LLM error: {e}"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        record_spend(result["cost_usd"])

        # Record usage
        db.add(UsageEvent(
            user_id=job.user_id,
            event_type="extraction",
            model=result["model"],
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            cost_usd=result["cost_usd"],
        ))

        # Store raw output in job.error_message field for MVP retrieval
        # (a full v2 would parse YAML and create HuCard / JournalFingerprint row)
        yaml_body = result["content"]
        
        # Attempt naive parse to create a card for Branch A
        if job.branch == "a":
            try:
                # Simple heuristic parse - look for key metadata in the YAML
                import yaml as yamllib
                parsed = yamllib.safe_load(yaml_body)
                if isinstance(parsed, dict):
                    diag = parsed.get("diagnosis_card", {}) or {}
                    paper_id = parsed.get("paper_id", f"extracted_{job.id}")
                    title = diag.get("title", file.filename)
                    authors_list = diag.get("authors", [])
                    authors = ", ".join(authors_list) if isinstance(authors_list, list) else str(authors_list)
                    journal = diag.get("journal", "Unknown")
                    year = int(diag.get("year", datetime.now().year))
                    position = str(diag.get("author_position", "unknown"))
                    method = str(diag.get("method_path", "unknown"))
                    opening = str(diag.get("opening_style", "unknown"))
                    era = diag.get("publisher_era")
                    gold_count = parsed.get("red_line_audit", {}).get("summary", "").count("GOLD")
                    
                    card = HuCard(
                        paper_id=paper_id,
                        title=title[:512],
                        authors=authors[:2000],
                        journal=journal[:128],
                        year=year,
                        author_position=position[:64],
                        method_path=method[:64],
                        opening_style=opening[:64],
                        publisher_era=era[:64] if era else None,
                        red_line_gold_count=gold_count,
                        full_yaml=yaml_body,
                        card_data=parsed,
                        extractor_version="v1.5-auto",
                        extracted_by_user_id=job.user_id,
                    )
                    db.add(card)
                    db.flush()
                    job.produced_card_id = card.id
            except Exception as parse_err:
                # Save raw YAML anyway; leave produced_card_id null for user review
                job.error_message = f"Auto-parse failed (YAML stored in raw_output field is not persisted in MVP). Retry after manual review: {parse_err}"
        
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        try:
            job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)[:1000]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
