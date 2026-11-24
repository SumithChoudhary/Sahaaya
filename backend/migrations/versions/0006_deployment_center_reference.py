"""Link manual deployment records to their stock center.

Revision ID: 0006_deployment_center_reference
Revises: 0005_center_resource_inventory
"""
from alembic import op
from sqlalchemy import Column, ForeignKey, Integer, inspect

revision = "0006_deployment_center_reference"
down_revision = "0005_center_resource_inventory"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {column["name"] for column in inspect(bind).get_columns("resource_allocations")}
    if "center_id" not in existing:
        op.add_column("resource_allocations", Column("center_id", Integer, ForeignKey("resource_centers.id"), nullable=True))
        op.create_index("ix_resource_allocations_center_id", "resource_allocations", ["center_id"])


def downgrade():
    raise RuntimeError("Deployment center provenance is retained; use a reviewed forward migration instead of removing it.")
