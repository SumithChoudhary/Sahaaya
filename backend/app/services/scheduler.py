from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from ..db import SessionLocal
from ..integrations.registry import configured_status
from ..models import DataSource
from .ingestion import run_ingestion


async def ingestion_scheduler() -> None:
    """Simple opt-in async scheduler; per-source DB leases protect multi-process runs."""
    interval = max(60, int(os.getenv("SAHAAYA_INGESTION_INTERVAL_SECONDS", "900")))
    while True:
        with SessionLocal() as db:
            sources = db.scalars(select(DataSource).where(DataSource.is_enabled.is_(True))).all()
            keys = [row.source_key for row in sources if configured_status(row)]
        if keys:
            await asyncio.gather(*(run_ingestion(key) for key in keys), return_exceptions=True)
        await asyncio.sleep(interval)
