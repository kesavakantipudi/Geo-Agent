"""Agricultural intelligence results (Phase 6A).

An ``AgriAnalysis`` row records one completed index computation for one scene
over one analysis session's AOI, together with the statistics, heuristic
vegetation-condition tiers, the exact thresholds used, the band assets that
produced it, and full processing provenance, so the result is reproducible from
(AOI, scene, index, algorithm version).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgriAnalysis(Base):
    __tablename__ = "agri_analyses"
    __table_args__ = (
        Index(
            "ix_agri_analyses_session_acquisition",
            "analysis_session_id",
            "acquisition_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_session_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[int] = mapped_column(
        ForeignKey("satellite_scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    index_name: Mapped[str] = mapped_column(String(50), nullable=False)
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)

    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    stddev_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_pixel_pct: Mapped[float] = mapped_column(Float, nullable=False)
    pixel_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    overall_tier: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dominant_tier: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Full statistics payload as returned at analysis time (matches the API).
    statistics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # {role -> {asset_key, retrieval_id}} for provenance.
    band_assets: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Full tier definitions (documented heuristic thresholds) used by the result.
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Index spec snapshot (formula, band roles, units, range).
    index_info: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Processing provenance (algorithm version, libraries, masking, window, area).
    processing: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Human-readable warnings surfaced alongside the result.
    warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
