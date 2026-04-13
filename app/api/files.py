"""
File upload routes.
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pathlib import Path
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, UploadedFile
from app.schemas.schemas import UploadedFilePublic
from app.core.deps import get_current_user
from app.core.config import settings
from app.services.file_parser import extract_text_from_bytes


router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=UploadedFilePublic)
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(413, f"File too large (max {settings.MAX_UPLOAD_SIZE_BYTES} bytes)")
    if len(content) == 0:
        raise HTTPException(400, "Empty file")

    # Extract text
    extracted = extract_text_from_bytes(content, file.filename or "")

    record = UploadedFile(
        user_id=user.id,
        filename=file.filename or "upload.bin",
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        extracted_text=extracted,
        storage_path=None,  # not keeping the binary; could store to S3/R2 in future
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    resp = UploadedFilePublic.model_validate(record)
    resp.has_extracted_text = bool(extracted and not extracted.startswith("["))
    return resp


@router.get("", response_model=list[UploadedFilePublic])
def list_files(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    files = db.query(UploadedFile).filter(UploadedFile.user_id == user.id).order_by(UploadedFile.id.desc()).all()
    out = []
    for f in files:
        item = UploadedFilePublic.model_validate(f)
        item.has_extracted_text = bool(f.extracted_text and not f.extracted_text.startswith("["))
        out.append(item)
    return out


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    f = db.query(UploadedFile).filter(UploadedFile.id == file_id, UploadedFile.user_id == user.id).first()
    if not f:
        raise HTTPException(404, "Not found")
    db.delete(f)
    db.commit()
    return {"ok": True}
