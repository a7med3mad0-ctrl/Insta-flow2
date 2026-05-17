from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class Config(Base):
    """Stores Instagram API credentials (single row)."""
    __tablename__ = "config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instagram_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Campaign(Base):
    """
    Links a post to trigger keywords, comment reply text, and DM message.
    keywords: comma-separated list, e.g. "info,link,price"
    """
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    post_id: Mapped[str] = mapped_column(String(64), nullable=False)
    post_thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=False)  # comma-separated
    comment_reply: Mapped[str] = mapped_column(Text, nullable=False)
    dm_message: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)

    def keyword_list(self) -> list[str]:
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]


class ProcessedComment(Base):
    """Deduplication table — tracks comment IDs already handled."""
    __tablename__ = "processed_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    campaign_id: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    commenter_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    matched_keyword: Mapped[str | None] = mapped_column(String(128), nullable=True)
    comment_reply_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    dm_sent: Mapped[bool] = mapped_column(Boolean, default=False)
