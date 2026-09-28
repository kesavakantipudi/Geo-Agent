"""agricultural intelligence: completed NDVI analyses with provenance

Phase 6A (Agri Intelligence): stores completed, deterministic spectral-index
analyses over retrieved Sentinel-2 band assets for an analysis session's AOI.
Each row keeps the statistics, documented heuristic tier thresholds, index
spec snapshot, band-asset provenance, and full processing metadata so results
are reproducible. Only *completed* analyses are persisted; computations that
cannot be carried out faithfully are returned as explicit "unavailable" API
states and are intentionally not stored.

Revision ID: 0005_agri_analyses
Revises: 0004_weather_observations
Create Date: 2026-09-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_agri_analyses"
down_revision: str | None = "0004_weather_observations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agri_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("analysis_session_id", sa.Integer(), nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("index_name", sa.String(length=50), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("cloud_cover", sa.Float(), nullable=True),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("mean_value", sa.Float(), nullable=True),
        sa.Column("median_value", sa.Float(), nullable=True),
        sa.Column("stddev_value", sa.Float(), nullable=True),
        sa.Column("valid_pixel_pct", sa.Float(), nullable=False),
        sa.Column("pixel_count", sa.BigInteger(), nullable=True),
        sa.Column("overall_tier", sa.String(length=30), nullable=True),
        sa.Column("dominant_tier", sa.String(length=30), nullable=True),
        sa.Column("statistics", postgresql.JSONB(), nullable=False),
        sa.Column("band_assets", postgresql.JSONB(), nullable=False),
        sa.Column("thresholds", postgresql.JSONB(), nullable=False),
        sa.Column("index_info", postgresql.JSONB(), nullable=False),
        sa.Column("processing", postgresql.JSONB(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_session_id"], ["analysis_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scene_id"], ["satellite_scenes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agri_analyses_analysis_session_id",
        "agri_analyses",
        ["analysis_session_id"],
    )
    op.create_index("ix_agri_analyses_scene_id", "agri_analyses", ["scene_id"])
    op.create_index("ix_agri_analyses_acquisition_date", "agri_analyses", ["acquisition_date"])
    op.create_index(
        "ix_agri_analyses_session_acquisition",
        "agri_analyses",
        ["analysis_session_id", "acquisition_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_agri_analyses_session_acquisition", table_name="agri_analyses")
    op.drop_index("ix_agri_analyses_acquisition_date", table_name="agri_analyses")
    op.drop_index("ix_agri_analyses_scene_id", table_name="agri_analyses")
    op.drop_index("ix_agri_analyses_analysis_session_id", table_name="agri_analyses")
    op.drop_table("agri_analyses")
