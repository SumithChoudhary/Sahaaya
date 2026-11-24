"""Add an extensible inventory ledger for center-scoped stock.

Revision ID: 0005_center_resource_inventory
Revises: 0004_incident_measurements
"""
from alembic import op

from backend.app.db import Base
from backend.app import models  # noqa: F401 - register metadata

revision = "0005_center_resource_inventory"
down_revision = "0004_incident_measurements"
branch_labels = None
depends_on = None


def upgrade():
    # Additive only. Existing resources and all operational records remain intact.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Center inventory records are operational history and are never removed by an automatic downgrade.")
