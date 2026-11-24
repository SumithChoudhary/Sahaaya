"""Add operator-authored disaster alerts and department coordination records."""
from alembic import op

from backend.app.db import Base
from backend.app import models  # noqa: F401 - register the added tables


revision = "0007_user_disaster_alerts"
down_revision = "0006_deployment_center_reference"
branch_labels = None
depends_on = None


def upgrade():
    # Earlier additive migrations also run create_all against current metadata.
    # checkfirst keeps this revision safe for both fresh and existing databases.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Disaster alert and task records are operational history; use a reviewed forward migration instead of deleting them.")
