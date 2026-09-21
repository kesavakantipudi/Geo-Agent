"""Agent execution results (schema foundation only; agents in Q2/Q3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentResult(Base):
    __tablename__ = "agent_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_request_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
