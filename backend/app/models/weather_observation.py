"""Weather observations and their analysis-session linkage (Phase 5).

Phase 5 persists *normalized* observations exactly as reported by a provider:

- One row per variable per sample time (``provider`` + ``observed_at`` +
  ``latitude`` + ``longitude`` + ``variable`` is unique).
- ``value`` is the provider's recorded value. Missing values stay ``NULL``
  and are never written as ``0`` (which would fabricate a measurement).
- Every row keeps its ``units``, ``units_doc``, ``model``, ``data_type``,
  ``timezone``, ``provenance`` and ``attribution`` so results can always be
  attributed and verified.

The columns created in Phase 2 (``temperature_c``, ``humidity_pct``,
``rainfall_mm``, ``wind_speed_ms``, ``pressure_hpa``, ``metadata``) are legacy
schema-foundation columns that were never populated. They are retained (as
nullable) so migration ``0004`` does not destroy anything and the ORM stays in
sync with the migrated database.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    __table_args__ = (
        # Provider + sample time (Phase 2 index, kept for legacy compatibility).
        Index("ix_weather_provider_time", "provider", "observed_at"),
        # Phase 5 upsert key: one row per variable per grid point per time.
        Index(
            "ix_weather_obs_point_variable",
            "provider",
            "observed_at",
            "latitude",
            "longitude",
            "variable",
        ),
        UniqueConstraint(
            "provider",
            "observed_at",
            "latitude",
            "longitude",
            "variable",
            name="uq_weather_obs_point_variable",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    # Phase 5 per-variable value. ``value`` is the recorded value; missing stays
    # NULL (never invented as ``0``).
    variable: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    units: Mapped[str | None] = mapped_column(String(50), nullable=True)
    units_doc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Legacy Phase 2 schema-foundation columns (never populated; retained).
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_hpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    discoveries: Mapped[list[WeatherObservationDiscovery]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
    )


class WeatherObservationDiscovery(Base):
    """Ties a weather observation to the analysis session whose AOI found it."""

    __tablename__ = "weather_observation_discoveries"
    __table_args__ = (
        UniqueConstraint(
            "observation_id", "analysis_session_id", name="uq_weather_discovery_obs_session"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("weather_observations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_session_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discovered_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    observation: Mapped[WeatherObservation] = relationship(back_populates="discoveries")
