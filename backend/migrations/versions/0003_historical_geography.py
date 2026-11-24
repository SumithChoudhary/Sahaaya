"""Retain coordinates and location labels for historical observations.

Revision ID: 0003_historical_geography
Revises: 0002_data_integration_foundation
"""
from alembic import op
from sqlalchemy import Column, Float, String, inspect

revision = "0003_historical_geography"
down_revision = "0002_data_integration_foundation"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {column["name"] for column in inspect(bind).get_columns("historical_observations")}
    for column in [Column("latitude", Float, nullable=True), Column("longitude", Float, nullable=True),
                   Column("location_name", String(180), nullable=True)]:
        if column.name not in existing:
            op.add_column("historical_observations", column)


def downgrade():
    raise RuntimeError("Historical location data is retained by design; use a reviewed forward migration rather than dropping it.")
