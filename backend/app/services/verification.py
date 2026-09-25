"""[PERSON 2] Round 1 — automatic system check of a submission.

TODO(Person 2): def run_system_check(db, submission) -> None
  Uses services.youtube.get_video_info() (Person 3). Checks, in order:
    1. platform is supported (config.SUPPORTED_SUBMISSION_PLATFORMS — YouTube only for now)
    2. video exists and is public
    3. video.channel_id == creator.youtube_channel_id   (creator must have connected YouTube)
    4. video.published_at >= campaign start (campaign.created_at, or funded time)
    5. not already submitted (same external_video_id) to this campaign
    6. view_count >= campaign.min_views (default 1,000)

  Result:
    * 1–5 fail                      -> status=rejected, rejected_by=system, rejection_reason=<why>
    * 1–5 pass, 6 not yet           -> stay pending (re-checked on every views refresh);
                                       reject with "not enough views" once the campaign deadline passes
    * all pass                      -> status=under_review, system_checked_at=now  (admin queue)
  Always store video_title / video_channel_id / video_published_at / view_count on the submission
  so the admin can see them in the review queue.
"""
