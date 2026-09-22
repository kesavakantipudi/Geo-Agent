"""weather observations: per-variable values, provenance, and session discoveries

Phase 5 (Weather Intelligence): the Phase 2 `weather_observations` placeholder
only had fixed columns (temperature/humidity/rainfall/wind/pressure + metadata)
and was never populated. Phase 5 switches to a per-variable observation record
carrying real provider values, units, units_doc, model, data type, timezone,
provenance, and attribution. The legacy columns are retained as nullable so no
existing data is erased and the migration stays safe on databases that already
created the base table.

Also adds `weather_observation_discoveries`, tying each observation to the
analysis session whose AOI discovered it (mirroring satellite_scene_discoveries).

Revision ID: 0004_weather_observations
Revises: 0003_satellite_scene_assets
Create Date: 2026-09-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_weather_observations"
down_revision: str | None = "0003_satellite_scene_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Phase 5 per-variable/provenance columns (nullable so databases that may
    # already hold rows in the legacy columns upgrade without failing).
    op.add_column(
        "weather_observations",
        sa.Column("variable", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("value", sa.Float(), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("units", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("units_doc", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("model", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("data_type", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("timezone", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("attribution", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_weather_obs_point_variable",
        "weather_observations",
        ["provider", "observed_at", "latitude", "longitude", "variable"],
    )
    op.create_unique_constraint(
        "uq_weather_obs_point_variable",
        "weather_observations",
        ["provider", "observed_at", "latitude", "longitude", "variable"],
    )

    op.create_table(
        "weather_observation_discoveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("observation_id", sa.Integer(), nullable=False),
        sa.Column("analysis_session_id", sa.Integer(), nullable=False),
        sa.Column("discovered_by", sa.Integer(), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_session_id"], ["analysis_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["discovered_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["weather_observations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observation_id", "analysis_session_id", name="uq_weather_discovery_obs_session"
        ),
    )
    op.create_index(
        "ix_weather_observation_discoveries_observation_id",
        "weather_observation_discoveries",
        ["observation_id"],
    )
    op.create_index(
        "ix_weather_observation_discoveries_analysis_session_id",
        "weather_observation_discoveries",
        ["analysis_session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weather_observation_discoveries_analysis_session_id",
        table_name="weather_observation_discoveries",
    )
    op.drop_index(
        "ix_weather_observation_discoveries_observation_id",
        table_name="weather_observation_discoveries",
    )
    op.drop_table("weather_observation_discoveries")

    op.drop_constraint("uq_weather_obs_point_variable", "weather_observations", type_="unique")
    op.drop_index("ix_weather_obs_point_variable", table_name="weather_observations")
    op.drop_column("weather_observations", "attribution")
    op.drop_column("weather_observations", "provenance")
    op.drop_column("weather_observations", "timezone")
    op.drop_column("weather_observations", "data_type")
    op.drop_column("weather_observations", "model")
    op.drop_column("weather_observations", "units_doc")
    op.drop_column("weather_observations", "units")
    op.drop_column("weather_observations", "value")
    op.drop_column("weather_observations", "variable")
