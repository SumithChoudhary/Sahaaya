from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from ..db import SessionLocal
from ..integrations.base import ProviderNotConfigured
from ..integrations.registry import connector_for
from ..integrations.http import validate_coordinates
from ..models import Alert, DataSource, GeographicLocation, Incident, IngestionLog, RawSourceRecord, WeatherObservation


def _json_hash(value: dict) -> str:
    packed = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def _store_raw(db, source: DataSource, item):
    digest = _json_hash(item.raw)
    old = db.scalar(select(RawSourceRecord).where(
        RawSourceRecord.source_id == source.id,
        RawSourceRecord.external_record_id == item.external_id,
        RawSourceRecord.content_hash == digest,
    ))
    if old:
        return old, True
    revision = (db.scalar(select(func.max(RawSourceRecord.revision)).where(
        RawSourceRecord.source_id == source.id,
        RawSourceRecord.external_record_id == item.external_id,
    )) or 0) + 1
    raw = RawSourceRecord(source_id=source.id, external_record_id=item.external_id, content_hash=digest,
        revision=revision, payload=item.raw, source_published_at=item.published_at,
        fetched_at=datetime.now(timezone.utc), source_url=item.source_url, quality_status="unreviewed")
    db.add(raw)
    db.flush()
    return raw, False


def _upsert_incident(db, source: DataSource, raw: RawSourceRecord, item):
    values = dict(item.values)
    row = db.scalar(select(Incident).where(Incident.source_id == source.id, Incident.external_record_id == item.external_id))
    if row is None:
        db.add(Incident(source_id=source.id, raw_record_id=raw.id, external_record_id=item.external_id, **values))
    else:
        row.raw_record_id = raw.id
        for key, value in values.items():
            setattr(row, key, value)

    if values.get("is_official_warning"):
        alert_id = f"CAP-{hashlib.sha256(item.external_id.encode()).hexdigest()[:24]}"
        alert = db.scalar(select(Alert).where(Alert.source_id == source.id, Alert.external_record_id == item.external_id))
        level = str(values.get("severity") or "Unknown").lower()
        if alert is None:
            db.add(Alert(alert_id=alert_id, severity=level, title=values.get("title", "Official warning"),
                message=values.get("description") or values.get("area_description") or "Official warning received; review the source record.",
                source_id=source.id, external_record_id=item.external_id, source_published_at=item.published_at,
                source_url=item.source_url, is_official=True, is_read=False,
                timestamp=item.published_at or datetime.now(timezone.utc)))
        else:
            alert.title = values.get("title", alert.title)
            alert.message = values.get("description") or values.get("area_description") or alert.message
            alert.severity = level
            alert.source_published_at = item.published_at
            alert.source_url = item.source_url


def _upsert_weather(db, source: DataSource, raw: RawSourceRecord, item):
    values = dict(item.values)
    try:
        numeric_value = float(values["value"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Normalized weather observation has no numeric value")
    if not math.isfinite(numeric_value):
        raise ValueError("Normalized weather observation must be finite")
    observed_at = values.get("observed_at")
    if not isinstance(observed_at, datetime):
        raise ValueError("Normalized weather observation has no valid timestamp")
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    if observed_at > datetime.now(timezone.utc):
        raise ValueError("Future-dated observations cannot be imported as measured data")
    latitude, longitude = values.get("latitude"), values.get("longitude")
    if latitude is not None or longitude is not None:
        coordinates = validate_coordinates(latitude, longitude)
        if coordinates is None:
            raise ValueError("Normalized observation coordinates are invalid")
        latitude, longitude = coordinates
    geo_source = f"provider:{source.source_key}"
    parent_id = None
    state_code = str(values.get("state_code") or values.get("state_name") or "").strip() or None
    district_code = str(values.get("district_code") or values.get("district_name") or "").strip() or None
    for level, code, name in [("state", state_code, values.get("state_name")), ("district", district_code, values.get("district_name"))]:
        if not code:
            continue
        location = db.scalar(select(GeographicLocation).where(GeographicLocation.source == geo_source,
            GeographicLocation.external_code == f"{level}:{code}"))
        if location is None:
            location = GeographicLocation(source=geo_source, external_code=f"{level}:{code}", name=str(name or code),
                level=level, parent_id=parent_id, country_code="IND", state_code=state_code,
                district_code=district_code, quality_status="unreviewed")
            db.add(location)
            db.flush()
        parent_id = location.id
    location_name = str(values.get("location_name") or "").strip() or None
    location_id = None
    if location_name or latitude is not None:
        code = location_name or f"{latitude:.5f},{longitude:.5f}"
        location = db.scalar(select(GeographicLocation).where(GeographicLocation.source == geo_source,
            GeographicLocation.external_code == f"station:{code}"))
        if location is None:
            location = GeographicLocation(source=geo_source, external_code=f"station:{code}",
                name=location_name or "Coordinate location", level="station", parent_id=parent_id,
                country_code="IND", state_code=state_code, district_code=district_code,
                latitude=latitude, longitude=longitude, quality_status="unreviewed")
            db.add(location)
            db.flush()
        location_id = location.id
    row = db.scalar(select(WeatherObservation).where(
        WeatherObservation.source_id == source.id, WeatherObservation.external_record_id == item.external_id,
        WeatherObservation.variable == str(values["variable"]), WeatherObservation.observed_at == observed_at,
    ))
    fields = {"raw_record_id": raw.id, "location_id": location_id, "variable": str(values["variable"]), "value": numeric_value,
        "unit": str(values["unit"]), "observed_at": observed_at, "fetched_at": datetime.now(timezone.utc),
        "latitude": latitude, "longitude": longitude,
        "quality_status": values.get("quality_status", "unreviewed"), "quality_notes": values.get("quality_notes")}
    if row is None:
        db.add(WeatherObservation(source_id=source.id, external_record_id=item.external_id, **fields))
    else:
        for key, value in fields.items():
            setattr(row, key, value)


async def run_ingestion(source_key: str) -> dict:
    """Run one provider with a DB lease so concurrent API/scheduler triggers do not overlap."""
    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        source = db.scalar(select(DataSource).where(DataSource.source_key == source_key))
        if source is None:
            return {"status": "not_found", "error": "Data source does not exist"}
        source.last_attempt_at = now
        connector = connector_for(source_key)
        if connector is None or not source.is_enabled or not connector.is_configured(source):
            source.status = "Not configured" if source.is_enabled else "Unavailable"
            source.last_error = "Connector is not configured" if source.is_enabled else "Source is disabled"
            log = IngestionLog(source_id=source.id, status="not_configured" if source.is_enabled else "disabled",
                               started_at=now, finished_at=now, message=source.last_error)
            db.add(log)
            db.commit()
            return {"status": log.status, "source_key": source_key, "message": log.message}

        expires = now + timedelta(minutes=5)
        result = db.execute(update(DataSource).where(
            DataSource.id == source.id,
            (DataSource.lease_expires_at.is_(None)) | (DataSource.lease_expires_at < now),
        ).values(lease_token=token, lease_expires_at=expires))
        if result.rowcount != 1:
            db.rollback()
            return {"status": "already_running", "source_key": source_key, "message": "An ingestion attempt is already active for this source."}
        log = IngestionLog(source_id=source.id, status="running", started_at=now)
        db.add(log)
        db.commit()
        source_id, previous_etag, endpoint = source.id, source.etag, source.endpoint

    with SessionLocal() as db:
        source = db.get(DataSource, source_id)
        log = db.scalar(select(IngestionLog).where(IngestionLog.source_id == source_id, IngestionLog.status == "running").order_by(IngestionLog.id.desc()))
        try:
            fetched = await connector.fetch(source, previous_etag)
            if fetched.not_modified:
                source.status = "Fresh"
                source.last_success_at = datetime.now(timezone.utc)
                source.last_error = None
                log.status, log.message = "not_modified", fetched.message
                log.fetched_count = log.imported_count = 0
            else:
                log.fetched_count = len(fetched.records)
                imported = duplicates = rejected = 0
                latest = None
                for item in fetched.records:
                    try:
                        raw, duplicate = _store_raw(db, source, item)
                        if duplicate:
                            normalized_exists = False
                            if item.kind == "incident":
                                normalized_exists = db.scalar(select(Incident.id).where(
                                    Incident.source_id == source.id, Incident.external_record_id == item.external_id)) is not None
                            elif item.kind == "weather":
                                observed = item.values.get("observed_at")
                                normalized_exists = db.scalar(select(WeatherObservation.id).where(
                                    WeatherObservation.source_id == source.id,
                                    WeatherObservation.external_record_id == item.external_id,
                                    WeatherObservation.variable == str(item.values.get("variable", "")),
                                    WeatherObservation.observed_at == observed)) is not None
                            else:
                                duplicates += 1
                                continue
                            if normalized_exists:
                                duplicates += 1
                                continue
                        if item.kind == "incident":
                            _upsert_incident(db, source, raw, item)
                        elif item.kind == "weather":
                            _upsert_weather(db, source, raw, item)
                        elif item.kind != "raw":
                            raise ValueError(f"Unknown normalized record type: {item.kind}")
                        imported += 1
                        if item.published_at and (latest is None or item.published_at > latest):
                            latest = item.published_at
                    except (ValueError, TypeError) as exc:
                        rejected += 1
                        log.details = {**(log.details or {}), "rejected_examples": [*(log.details or {}).get("rejected_examples", [])[:9], str(exc)[:300]]}
                source.etag = fetched.etag or source.etag
                source.status = "Fresh"
                source.last_success_at = datetime.now(timezone.utc)
                source.latest_observation_at = latest or fetched.source_timestamp or source.latest_observation_at
                source.last_record_count = imported
                source.last_error = None
                log.status, log.message = "completed", fetched.message
                log.imported_count, log.duplicate_count, log.rejected_count = imported, duplicates, rejected
            log.finished_at = datetime.now(timezone.utc)
            db.execute(update(DataSource).where(DataSource.id == source_id, DataSource.lease_token == token)
                .values(lease_token=None, lease_expires_at=None))
            db.commit()
            return {"status": log.status, "source_key": source_key, "fetched": log.fetched_count,
                    "imported": log.imported_count, "duplicates": log.duplicate_count, "rejected": log.rejected_count,
                    "message": log.message}
        except ProviderNotConfigured as exc:
            log.status, log.message, log.finished_at = "not_configured", str(exc), datetime.now(timezone.utc)
            source.status, source.last_error = "Not configured", str(exc)
        except Exception as exc:
            log.status, log.error, log.finished_at = "failed", f"{type(exc).__name__}: {str(exc)[:500]}", datetime.now(timezone.utc)
            source.status, source.last_error = "Unavailable", log.error
        db.execute(update(DataSource).where(DataSource.id == source_id, DataSource.lease_token == token)
            .values(lease_token=None, lease_expires_at=None))
        db.commit()
        return {"status": log.status, "source_key": source_key, "error": log.error or log.message}
