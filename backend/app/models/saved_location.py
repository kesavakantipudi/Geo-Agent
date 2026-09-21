"""Saved geographic locations (user-authored, no geocoding yet)."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin


class SavedLocation(TimestampMixin, Base):
    __tablename__ = "saved_locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    location_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="custom")
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    # PostGIS geometry (SRID 4326). Accepts point/polygon/etc. via EWKT or GeoJSON.
    geometry = mapped_column(Geometry(srid=4326, spatial_index=True), nullable=True)
