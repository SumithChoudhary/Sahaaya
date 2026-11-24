"""Add source provenance, observations, geography and assessment history.

Revision ID: 0002_data_integration_foundation
Revises: 0001_initial_schema
"""
from alembic import op
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, inspect

from backend.app.db import Base
from backend.app import models  # noqa: F401 - register the full metadata

revision = "0002_data_integration_foundation"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # create_all is used only to add missing tables; it never drops existing data.
    Base.metadata.create_all(bind=bind, checkfirst=True)
    existing = {column["name"] for column in inspect(bind).get_columns("alerts")}
    additions = [
        Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=True),
        Column("external_record_id", String(200), nullable=True),
        Column("source_published_at", DateTime(timezone=True), nullable=True),
        Column("source_url", Text, nullable=True),
        Column("is_official", Boolean, nullable=False, server_default="0"),
    ]
    for column in additions:
        if column.name not in existing:
            op.add_column("alerts", column)

    source_columns = {column["name"] for column in inspect(bind).get_columns("data_sources")}
    for column in [
        Column("lease_token", String(64), nullable=True),
        Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    ]:
        if column.name not in source_columns:
            op.add_column("data_sources", column)


def downgrade():
    raise RuntimeError("This data integration migration is non-destructive. Do not drop imported or provenance data as a rollback strategy.")
