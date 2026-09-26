"""[PERSON 2] Round 1 — automatic system check of a submission.

run_system_check(db, submission) -> None
  Uses services.youtube.get_video_info() (Person 3). Checks, in order:
    1. platform is supported (config.SUPPORTED_SUBMISSION_PLATFORMS — YouTube only for now)
    2. video exists and is public
    3. video.channel_id == creator.youtube_channel_id   (creator must have connected YouTube)
    4. video.published_at >= campaign start
    5. not already submitted (same external_video_id) to this campaign
    6. view_count >= campaign.min_views (default 1,000)

  Result:
    * 1–5 fail                      -> status=rejected, rejected_by=system, rejection_reason=<why>
    * 1–5 pass, 6 not yet           -> stay pending (re-checked on every views refresh);
                                       reject with "not enough views" once the campaign deadline passes
    * all pass                      -> status=under_review, system_checked_at=now  (admin queue)
  Always store video_title / video_channel_id / video_published_at / view_count on the submission
  so the admin can see them in the review queue.

  Called only by app.services.youtube.refresh_views() and routers/submissions.py — both manage
  their own db.commit(); this function only db.flush()es so it never breaks their transaction.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SUPPORTED_SUBMISSION_PLATFORMS
from app.models.campaign import Campaign
from app.models.submission import RejectedBy, Submission, SubmissionStatus
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services import youtube as yt


def _campaign_start(db: Session, campaign: Campaign) -> datetime:
    """When the campaign actually opened for submissions.

    A campaign only accepts submissions once funded/active (routers/submissions.py enforces
    that), so the mock checkout's Transaction is the true "start" — campaign.created_at is just
    when the brand saved the draft, which can be long before funding. Falls back to created_at
    if, for some reason, no funding transaction exists yet.
    """
    funded_at = db.scalar(
        select(Transaction.created_at)
        .where(Transaction.campaign_id == campaign.id, Transaction.type == TransactionType.campaign_fund)
        .order_by(Transaction.created_at.asc())
        .limit(1)
    )
    return funded_at or campaign.created_at


def run_system_check(db: Session, submission: Submission) -> None:
    campaign = db.get(Campaign, submission.campaign_id)
    creator = db.get(User, submission.creator_id)

    def reject(reason: str) -> None:
        submission.status = SubmissionStatus.rejected
        submission.rejected_by = RejectedBy.system
        submission.rejection_reason = reason
        submission.system_checked_at = datetime.now(timezone.utc)

    # 1) platform supported
    if submission.platform not in SUPPORTED_SUBMISSION_PLATFORMS:
        return reject(f"Platform '{submission.platform}' is not supported yet")

    # 2) video exists, is public
    info = yt.get_video_info(submission.external_video_id) if submission.external_video_id else None
    if info is None:
        return reject("Video not found or is private")

    # Store the latest known data regardless of outcome — the admin queue needs it.
    submission.video_title = info.title[:300]
    submission.video_channel_id = info.channel_id
    submission.video_published_at = info.published_at
    submission.view_count = info.view_count

    if not info.is_public:
        return reject("Video is not public")

    # 3) ownership
    if not creator.youtube_channel_id or info.channel_id != creator.youtube_channel_id:
        return reject("Video does not belong to your connected YouTube channel")

    # 4) published after campaign start
    campaign_start = _campaign_start(db, campaign)
    if info.published_at < campaign_start:
        return reject("Video was published before the campaign started")

    # 5) no duplicate submission of this video in this campaign
    duplicate = db.scalar(
        select(Submission.id).where(
            Submission.campaign_id == submission.campaign_id,
            Submission.external_video_id == submission.external_video_id,
            Submission.id != submission.id,
        )
    )
    if duplicate is not None:
        return reject("This video was already submitted to this campaign")

    # 6) minimum views
    if info.view_count < campaign.min_views:
        if campaign.deadline and datetime.now(timezone.utc) > campaign.deadline:
            return reject("Campaign ended before reaching the minimum views")
        # Not enough views yet — stay pending, re-checked on the next views refresh.
        submission.system_checked_at = datetime.now(timezone.utc)
        return

    submission.status = SubmissionStatus.under_review
    submission.system_checked_at = datetime.now(timezone.utc)
