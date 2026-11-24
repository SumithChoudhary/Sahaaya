"""Store provider magnitude, depth and update time on normalized incidents.

Revision ID: 0004_incident_measurements
Revises: 0003_historical_geography
"""
from alembic import op
from sqlalchemy import Column, DateTime, Float, inspect

revision = "0004_incident_measurements"
down_revision = "0003_historical_geography"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {column["name"] for column in inspect(bind).get_columns("incidents")}
    for column in [Column("magnitude", Float, nullable=True), Column("depth_km", Float, nullable=True),
                   Column("source_updated_at", DateTime(timezone=True), nullable=True)]:
        if column.name not in existing:
            op.add_column("incidents", column)


def downgrade():
    raise RuntimeError("Provider incident measurements are preserved; use a reviewed forward migration instead of removing sourced values.")
