"""add phase 3 analysis configuration to analysis_sessions

Phase 3 (Location Intelligence): sessions now store the AOI geometry (SRID
4326), the analysis date range, and the selected agents (JSONB array of codes).
All new columns are nullable, so this is a backward-compatible additive change.

Revision ID: 0002_analysis_session_config
Revises: 0001_initial
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_analysis_session_config"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_sessions",
        sa.Column("aoi_geometry", geoalchemy2.Geometry(srid=4326), nullable=True),
    )
    op.add_column("analysis_sessions", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("analysis_sessions", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column(
        "analysis_sessions",
        sa.Column("agents", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_analysis_sessions_aoi_geometry",
        "analysis_sessions",
        ["aoi_geometry"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analysis_sessions_aoi_geometry",
        table_name="analysis_sessions",
        postgresql_using="gist",
    )
    op.drop_column("analysis_sessions", "agents")
    op.drop_column("analysis_sessions", "end_date")
    op.drop_column("analysis_sessions", "start_date")
    op.drop_column("analysis_sessions", "aoi_geometry")
