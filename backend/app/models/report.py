"""Generated report records (schema foundation only; generation in Q4)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_format: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pdf")
    # pending | generating | ready | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
