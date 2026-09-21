"""Satellite scene metadata, assets, retrievals, and session linkage.

Scenes are upserted from provider STAC search results (unique per provider +
scene id). Asset and retrieval records are added lazily; signed download URLs
are generated on demand and are never persisted.
"""

from __future__ import annotations

from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class SatelliteScene(Base):
    __tablename__ = "satellite_scenes"
    __table_args__ = (UniqueConstraint("provider", "scene_id", name="uq_sat_provider_scene"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    scene_id: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry = mapped_column(Geometry(srid=4326, spatial_index=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assets: Mapped[list[SatelliteSceneAsset]] = relationship(
        back_populates="scene",
        cascade="all, delete-orphan",
        order_by="SatelliteSceneAsset.asset_key",
    )
    retrievals: Mapped[list[SatelliteRetrieval]] = relationship(
        back_populates="scene", cascade="all, delete-orphan"
    )
    discoveries: Mapped[list[SatelliteSceneDiscovery]] = relationship(
        back_populates="scene", cascade="all, delete-orphan"
    )


class SatelliteSceneAsset(Base):
    """A single data asset of a scene (e.g. a COG or a SAFE archive URL)."""

    __tablename__ = "satellite_scene_assets"
    __table_args__ = (
        UniqueConstraint("scene_id", "asset_key", name="uq_sat_asset_scene_key"),
        Index("ix_sat_asset_scene", "scene_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scene_id: Mapped[int] = mapped_column(
        ForeignKey("satellite_scenes.id", ondelete="CASCADE"), nullable=False
    )
    # Stable, provider-relative key ("visual", "B08", "tiles"...) per STAC assets.
    asset_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # Static (unsigned) URL. Signed access is appended at retrieval time.
    href: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scene: Mapped[SatelliteScene] = relationship(back_populates="assets")


class SatelliteRetrieval(TimestampMixin, Base):
    """An on-demand download of one asset for a scene (bounded, per request)."""

    __tablename__ = "satellite_retrievals"
    __table_args__ = (Index("ix_sat_retrieval_scene_session", "scene_id", "analysis_session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scene_id: Mapped[int] = mapped_column(
        ForeignKey("satellite_scenes.id", ondelete="CASCADE"), nullable=False
    )
    analysis_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requested_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    asset_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # queued | completed | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    # Path of the stored file, relative to the retrieval storage directory.
    stored_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scene: Mapped[SatelliteScene] = relationship(back_populates="retrievals")


class SatelliteSceneDiscovery(Base):
    """Ties a discovered scene to the analysis session whose AOI found it."""

    __tablename__ = "satellite_scene_discoveries"
    __table_args__ = (
        UniqueConstraint("scene_id", "analysis_session_id", name="uq_sat_discovery_scene_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scene_id: Mapped[int] = mapped_column(
        ForeignKey("satellite_scenes.id", ondelete="CASCADE"), nullable=False, index=True
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

    scene: Mapped[SatelliteScene] = relationship(back_populates="discoveries")
