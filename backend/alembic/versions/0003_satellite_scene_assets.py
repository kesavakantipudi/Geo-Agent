"""add satellite assets, retrievals, and scene-session discoveries

Phase 4 (Satellite Intelligence): scenes discovered through the analysis-session
workflow are linked to sessions via a join table, assets are stored as static
(unsigned) hrefs (signed access is generated on demand and never persisted),
and bounded on-demand retrievals are tracked per scene/session/key.

Revision ID: 0003_satellite_scene_assets
Revises: 0002_analysis_session_config
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_satellite_scene_assets"
down_revision: str | None = "0002_analysis_session_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "satellite_scene_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=False),
        sa.Column("asset_key", sa.String(length=100), nullable=False),
        sa.Column("href", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["scene_id"], ["satellite_scenes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scene_id", "asset_key", name="uq_sat_asset_scene_key"),
    )
    op.create_index("ix_sat_asset_scene", "satellite_scene_assets", ["scene_id"])

    op.create_table(
        "satellite_retrievals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=False),
        sa.Column("analysis_session_id", sa.Integer(), nullable=True),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("asset_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("stored_path", sa.String(length=500), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["analysis_session_id"], ["analysis_sessions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scene_id"], ["satellite_scenes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sat_retrieval_scene_session",
        "satellite_retrievals",
        ["scene_id", "analysis_session_id"],
    )
    op.create_index(
        "ix_satellite_retrievals_analysis_session_id",
        "satellite_retrievals",
        ["analysis_session_id"],
    )

    op.create_table(
        "satellite_scene_discoveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["scene_id"], ["satellite_scenes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scene_id", "analysis_session_id", name="uq_sat_discovery_scene_session"
        ),
    )
    op.create_index(
        "ix_satellite_scene_discoveries_scene_id", "satellite_scene_discoveries", ["scene_id"]
    )
    op.create_index(
        "ix_satellite_scene_discoveries_analysis_session_id",
        "satellite_scene_discoveries",
        ["analysis_session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_satellite_scene_discoveries_analysis_session_id",
        table_name="satellite_scene_discoveries",
    )
    op.drop_index(
        "ix_satellite_scene_discoveries_scene_id", table_name="satellite_scene_discoveries"
    )
    op.drop_table("satellite_scene_discoveries")

    op.drop_index("ix_satellite_retrievals_analysis_session_id", table_name="satellite_retrievals")
    op.drop_index("ix_sat_retrieval_scene_session", table_name="satellite_retrievals")
    op.drop_table("satellite_retrievals")

    op.drop_index("ix_sat_asset_scene", table_name="satellite_scene_assets")
    op.drop_table("satellite_scene_assets")
