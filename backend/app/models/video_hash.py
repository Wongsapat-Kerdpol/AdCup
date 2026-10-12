from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VideoHash(Base):
    """dHash fingerprint of one picture of a submitted video (duplicate-clip checker).

    Up to 4 rows per submission: the cover (hqdefault) and YouTube's 3 auto frames (1/2/3.jpg).
    `value` is the unsigned 64-bit hash stored as a signed BIGINT (see services/duplicate_check.py).
    """

    __tablename__ = "video_hashes"
    __table_args__ = (UniqueConstraint("submission_id", "frame"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    frame: Mapped[str] = mapped_column(String(16))  # "hqdefault" | "1" | "2" | "3"
    value: Mapped[int] = mapped_column(BigInteger)
    mirrored_value: Mapped[int] = mapped_column(BigInteger)  # hash of the left-right flipped picture
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
