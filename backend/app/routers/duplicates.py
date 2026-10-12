"""[ANTI-FRAUD] Duplicate-clip warnings for the admin review queue.

  GET /api/admin/duplicates/stats            — size of the fingerprint index
  GET /api/admin/duplicates/{submission_id}  — possible originals of this submission, most suspicious
                                               first (see services/duplicate_check.py)
Turned off with ENABLE_ANTI_FRAUD=false.
"""

import logging
from dataclasses import asdict

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_role
from app.models.submission import Submission
from app.models.user import User, UserRole
from app.schemas.duplicate import DuplicateIndexStats, DuplicateReport
from app.services import duplicate_check

router = APIRouter(prefix="/api/admin/duplicates", tags=["duplicate check (anti-fraud)"])
log = logging.getLogger(__name__)


@router.get("/stats", response_model=DuplicateIndexStats)
def stats(_: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    return duplicate_check.index_stats(db)


@router.get("/{submission_id}", response_model=DuplicateReport)
def check(submission_id: int, _: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    if not settings.enable_anti_fraud:
        return DuplicateReport(enabled=False, status="disabled")
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    try:
        report = duplicate_check.check_submission(db, submission)
        db.commit()
    except httpx.HTTPError as exc:
        # A warning helper must never block the review: just say we couldn't check.
        db.rollback()
        log.warning("duplicate check for submission %s failed: %s", submission_id, exc)
        return DuplicateReport(status="unavailable")
    return DuplicateReport.model_validate(asdict(report))
