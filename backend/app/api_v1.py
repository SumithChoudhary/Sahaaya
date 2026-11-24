from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from .db import get_db
from .integrations.http import parse_datetime, validate_coordinates
from .integrations.registry import configured_status, connector_for
from .models import (AffectedArea, Alert, DataSource, Deployment, GeographicLocation, HistoricalObservation, ResourceInventory,
                     AuditEvent, Incident, IngestionLog, RawSourceRecord, Resource, ResourceCenter, RiverObservation,
                     WeatherObservation, utcnow)
from .security import User, current_user, require_roles
from .services.ingestion import run_ingestion
from .services.optimizer import RESOURCE_KEYS

router = APIRouter(prefix="/api/v1")


class HistoricalImportMapping(BaseModel):
    timestamp_column: str = Field(min_length=1, max_length=160)
    value_column: str = Field(min_length=1, max_length=160)
    variable: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=40)
    id_column: str | None = Field(default=None, max_length=160)
    hazard_type: str | None = Field(default=None, max_length=80)
    location_column: str | None = Field(default=None, max_length=160)
    latitude_column: str | None = Field(default=None, max_length=160)
    longitude_column: str | None = Field(default=None, max_length=160)
    state_column: str | None = Field(default=None, max_length=160)
    state_code_column: str | None = Field(default=None, max_length=160)
    district_column: str | None = Field(default=None, max_length=160)
    district_code_column: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def coordinate_columns_pair(self):
        if bool(self.latitude_column) != bool(self.longitude_column):
            raise ValueError("Latitude and longitude columns must be supplied together")
        return self


class AlertReview(BaseModel):
    status: str = Field(pattern=r"^(reviewed|confirmed|dismissed)$")
    note: str | None = Field(default=None, max_length=1000)


class SourceConfiguration(BaseModel):
    endpoint: str | None = Field(default=None, max_length=1200)
    enabled: bool = True
    column_mapping: dict[str, str] | None = None


class InventoryInput(BaseModel):
    center_id: int = Field(ge=1)
    resource_key: str = Field(min_length=2, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    total: int = Field(ge=0)
    available: int = Field(ge=0)
    allocated: int = Field(default=0, ge=0)
    deployed: int = Field(default=0, ge=0)
    unit: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def quantities_fit_total(self):
        if self.available + self.allocated + self.deployed > self.total:
            raise ValueError("Available, allocated, and deployed quantities cannot exceed total inventory")
        return self


class InventoryUpdate(BaseModel):
    total: int | None = Field(default=None, ge=0)
    available: int | None = Field(default=None, ge=0)
    allocated: int | None = Field(default=None, ge=0)
    deployed: int | None = Field(default=None, ge=0)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    unit: str | None = Field(default=None, min_length=1, max_length=40)


def _source_health(source: DataSource) -> str:
    if source.source_key == "historical_import":
        return "Fresh" if source.last_success_at else "Not configured"
    if not source.is_enabled:
        return "Unavailable"
    if not configured_status(source):
        return "Not configured"
    if source.last_success_at is None:
        return "Unavailable"
    last_success = source.last_success_at
    if last_success.tzinfo is None:
        last_success = last_success.replace(tzinfo=timezone.utc)
    age = (utcnow() - last_success.astimezone(timezone.utc)).total_seconds()
    if age <= source.freshness_seconds:
        return "Fresh"
    if age <= source.freshness_seconds * 2:
        return "Delayed"
    return "Stale"


def _source_out(source: DataSource) -> dict:
    return {"id": source.id, "source_key": source.source_key, "name": source.name, "provider": source.provider,
            "category": source.category, "coverage": source.coverage, "endpoint": source.endpoint,
            "license_name": source.license_name, "license_url": source.license_url, "attribution": source.attribution,
            "is_enabled": source.is_enabled, "requires_credentials": source.requires_credentials,
            "credential_configured": source.credential_configured, "status": _source_health(source),
            "config": source.config or {},
            "last_attempt_at": source.last_attempt_at, "last_success_at": source.last_success_at,
            "latest_observation_at": source.latest_observation_at, "last_record_count": source.last_record_count,
            "last_error": source.last_error}


def _date_filters(query, model, start_at, end_at):
    if start_at:
        query = query.where(model.observed_at >= start_at)
    if end_at:
        query = query.where(model.observed_at <= end_at)
    return query


@router.get("/sources")
def list_sources(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [_source_out(source) for source in db.scalars(select(DataSource).order_by(DataSource.provider, DataSource.name)).all()]


@router.get("/sources/status")
def source_status(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [_source_out(source) for source in db.scalars(select(DataSource).order_by(DataSource.provider, DataSource.name)).all()]


@router.put("/sources/{source_key}/config")
def configure_source(source_key: str, payload: SourceConfiguration, db: Session = Depends(get_db), _: User = Depends(require_roles("Administrator"))):
    source = db.scalar(select(DataSource).where(DataSource.source_key == source_key))
    if source is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    permitted_hosts = {
        "nwic_telangana_rainfall": {"nwdp.nwic.gov.in", "www.nwdp.nwic.gov.in"},
        "cwc_flood_forecast": {"ffs.india-water.gov.in", "aff.india-water.gov.in", "inf.cwc.gov.in"},
    }
    if payload.endpoint is not None:
        parsed = urlsplit(payload.endpoint)
        if parsed.scheme != "https" or parsed.hostname not in permitted_hosts.get(source_key, set()) or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise HTTPException(status_code=422, detail="Only an HTTPS source host verified for this provider can be configured here")
        source.endpoint = payload.endpoint
    source.is_enabled = payload.enabled
    if payload.column_mapping is not None:
        if source_key != "nwic_telangana_rainfall":
            raise HTTPException(status_code=422, detail="Column mapping is currently supported only for NWIC rainfall CSV resources")
        allowed = {"id", "observed_at", "value", "unit", "variable", "latitude", "longitude", "station", "station_name", "state", "state_code", "district", "district_code"}
        if set(payload.column_mapping) - allowed or any(not isinstance(value, str) or len(value) > 160 for value in payload.column_mapping.values()):
            raise HTTPException(status_code=422, detail="Column mapping keys or values are invalid")
        source.config = {**(source.config or {}), "column_mapping": payload.column_mapping}
    source.status = "Not configured"
    source.last_error = None
    db.commit()
    db.refresh(source)
    return _source_out(source)


def _inventory_out(item: ResourceInventory) -> dict:
    return {"id": item.id, "center_id": item.center_id, "center_name": item.center.name,
        "resource_key": item.resource_key, "name": item.name, "total": item.total,
        "available": item.available, "allocated": item.allocated, "deployed": item.deployed,
        "remaining": max(item.total - item.deployed, 0), "unit": item.unit,
        "quality_status": item.quality_status, "updated_at": item.updated_at}


def _sync_legacy_resource_summary(db: Session, resource_key: str) -> None:
    rows = db.scalars(select(ResourceInventory).where(ResourceInventory.resource_key == resource_key)).all()
    legacy = db.scalar(select(Resource).where(Resource.resource_key == resource_key))
    if legacy is None or not rows:
        return
    legacy.total = sum(row.total for row in rows)
    legacy.available = sum(row.available for row in rows)
    legacy.allocated = sum(row.allocated for row in rows)
    legacy.deployed = sum(row.deployed for row in rows)
    legacy.center_id = rows[0].center_id if len(rows) == 1 else None


@router.get("/resource-inventory")
def list_center_inventory(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [_inventory_out(item) for item in db.scalars(select(ResourceInventory).order_by(ResourceInventory.center_id, ResourceInventory.name)).all()]


@router.post("/resource-inventory", status_code=201)
def create_center_inventory(payload: InventoryInput, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    if payload.resource_key not in RESOURCE_KEYS:
        raise HTTPException(status_code=422, detail=f"Supported resource keys are: {', '.join(RESOURCE_KEYS)}")
    center = db.get(ResourceCenter, payload.center_id)
    if center is None:
        raise HTTPException(status_code=404, detail="Resource center not found")
    duplicate = db.scalar(select(ResourceInventory.id).where(ResourceInventory.center_id == payload.center_id,
        ResourceInventory.resource_key == payload.resource_key))
    if duplicate:
        raise HTTPException(status_code=409, detail="That resource type already has an inventory row at this center")
    item = ResourceInventory(**payload.model_dump(), quality_status="manually_verified")
    db.add(item)
    db.add(AuditEvent(category="resource.inventory.created", summary=f"Added {item.name} at {center.name}",
        details={"center_id": center.id, "resource_key": item.resource_key, "available": item.available}, user_id=user.id))
    legacy = db.scalar(select(Resource).where(Resource.resource_key == item.resource_key))
    if legacy is None:
        db.add(Resource(resource_key=item.resource_key, name=item.name, total=item.total, available=item.available,
            allocated=item.allocated, deployed=item.deployed, unit=item.unit, center_id=item.center_id))
    db.flush()
    _sync_legacy_resource_summary(db, item.resource_key)
    db.commit()
    db.refresh(item)
    return _inventory_out(item)


@router.patch("/resource-inventory/{inventory_id}")
def update_center_inventory(inventory_id: int, payload: InventoryUpdate, db: Session = Depends(get_db),
                            user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    item = db.get(ResourceInventory, inventory_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Center inventory row not found")
    values = payload.model_dump(exclude_unset=True)
    quantities = {key: values.get(key, getattr(item, key)) for key in ("total", "available", "allocated", "deployed")}
    if quantities["available"] + quantities["allocated"] + quantities["deployed"] > quantities["total"]:
        raise HTTPException(status_code=422, detail="Available, allocated, and deployed quantities cannot exceed total inventory")
    for key, value in values.items():
        setattr(item, key, value)
    item.quality_status = "manually_verified"
    db.add(AuditEvent(category="resource.inventory.updated", summary=f"Updated {item.name} at {item.center.name}",
        details={"inventory_id": item.id, "resource_key": item.resource_key, "changed": list(values)}, user_id=user.id))
    _sync_legacy_resource_summary(db, item.resource_key)
    db.commit()
    db.refresh(item)
    return _inventory_out(item)


@router.get("/ingestion/logs")
def ingestion_logs(source_key: str | None = None, status: str | None = None, page: int = Query(1, ge=1),
                   page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(IngestionLog).join(DataSource)
    if source_key:
        query = query.where(DataSource.source_key == source_key)
    if status:
        query = query.where(IngestionLog.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(IngestionLog.started_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": row.id, "source_key": row.source.source_key if row.source else None, "status": row.status,
            "started_at": row.started_at, "finished_at": row.finished_at, "fetched_count": row.fetched_count,
            "imported_count": row.imported_count, "duplicate_count": row.duplicate_count,
            "rejected_count": row.rejected_count, "message": row.message, "error": row.error} for row in rows],
            "page": page, "page_size": page_size, "total": total}


@router.post("/sources/{source_key}/ingest")
async def trigger_ingestion(source_key: str, _: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    result = await run_ingestion(source_key)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=result.get("error"))
    if result["status"] == "already_running":
        raise HTTPException(status_code=409, detail=result["message"])
    return result


def _location_filter(query, location_model, state: str | None, district: str | None):
    if state or district:
        query = query.join(GeographicLocation, location_model.location_id == GeographicLocation.id)
        if state:
            query = query.where(GeographicLocation.state_code == state)
        if district:
            query = query.where(GeographicLocation.district_code == district)
    return query


@router.get("/alerts")
def official_alerts(state: str | None = None, severity: str | None = None, start_at: datetime | None = None,
                    end_at: datetime | None = None, limit: int = Query(100, ge=1, le=500),
                    db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(Incident).where(Incident.is_official_warning.is_(True))
    if severity:
        query = query.where(Incident.severity == severity)
    if start_at:
        query = query.where(Incident.source_published_at >= start_at)
    if end_at:
        query = query.where(Incident.source_published_at <= end_at)
    if state:
        query = _location_filter(query, Incident, state, None)
    rows = db.scalars(query.order_by(Incident.source_published_at.desc()).limit(limit)).all()
    return [_incident_out(row) for row in rows]


@router.post("/alerts/{alert_id}/review")
def review_official_alert(alert_id: int, payload: AlertReview, db: Session = Depends(get_db),
                          user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    row = db.get(Incident, alert_id)
    if row is None or not row.is_official_warning:
        raise HTTPException(status_code=404, detail="Official alert not found")
    previous = row.status
    row.status = payload.status
    db.add(AuditEvent(category="official_alert.reviewed", summary=f"Official warning {payload.status}",
                      details={"incident_id": row.id, "previous_status": previous, "note": payload.note}, user_id=user.id))
    db.commit()
    return {"id": row.id, "status": row.status, "reviewed_by": user.name, "human_review_required": True}


@router.post("/optimization/run")
def run_optimization_v1(payload: dict, db: Session = Depends(get_db),
                         user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    from .main import run_optimization
    from .schemas import OptimizationInput
    try:
        parsed = OptimizationInput.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc
    return run_optimization(parsed, db, user)


@router.post("/optimization/{run_id}/approve")
def approve_optimization_v1(run_id: int, payload: dict, db: Session = Depends(get_db),
                            user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    from .main import approve
    from .schemas import AllocationChange
    try:
        parsed = AllocationChange.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc
    return approve(run_id, parsed, db, user)


def _incident_out(row: Incident) -> dict:
    return {"id": row.id, "source_key": row.source.source_key if row.source else None,
            "external_record_id": row.external_record_id, "hazard_type": row.hazard_type, "title": row.title,
            "description": row.description, "severity": row.severity, "magnitude": row.magnitude,
            "depth_km": row.depth_km, "urgency": row.urgency, "certainty": row.certainty,
            "status": row.status, "is_official_warning": row.is_official_warning, "latitude": row.latitude,
            "longitude": row.longitude, "geometry": row.geometry, "area_description": row.area_description,
            "source_published_at": row.source_published_at, "source_updated_at": row.source_updated_at, "effective_at": row.effective_at,
            "expires_at": row.expires_at, "source_url": row.source_url, "data_quality": "unreviewed source record"}


@router.get("/incidents")
def list_incidents(hazard_type: str | None = None, severity: str | None = None, state: str | None = None,
                   district: str | None = None, start_at: datetime | None = None, end_at: datetime | None = None,
                   page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
                   db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(Incident)
    if hazard_type:
        query = query.where(Incident.hazard_type == hazard_type)
    if severity:
        query = query.where(Incident.severity == severity)
    if start_at:
        query = query.where(Incident.source_published_at >= start_at)
    if end_at:
        query = query.where(Incident.source_published_at <= end_at)
    query = _location_filter(query, Incident, state, district)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Incident.source_published_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_incident_out(row) for row in rows], "page": page, "page_size": page_size, "total": total}


def _observation_out(row) -> dict:
    source = row.source if hasattr(row, "source") else None
    location = row.location if hasattr(row, "location") else None
    return {"id": row.id, "source_key": source.source_key if source else None, "external_record_id": row.external_record_id,
            "variable": row.variable, "value": row.value, "unit": row.unit, "observed_at": row.observed_at,
            "fetched_at": row.fetched_at, "latitude": row.latitude, "longitude": row.longitude,
            "location_name": location.name if location else getattr(row, "location_name", None),
            "state_code": location.state_code if location else None, "district_code": location.district_code if location else None,
            "quality_status": row.quality_status, "quality_notes": row.quality_notes,
            "source_attribution": source.attribution if source else None}


def _filtered_weather(db, variable, state, district, start_at, end_at, page, page_size):
    query = select(WeatherObservation)
    if variable:
        query = query.where(WeatherObservation.variable == variable)
    query = _date_filters(query, WeatherObservation, start_at, end_at)
    query = _location_filter(query, WeatherObservation, state, district)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(WeatherObservation.observed_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_observation_out(row) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.get("/observations/weather")
def weather_observations(variable: str | None = None, state: str | None = None, district: str | None = None,
                         start_at: datetime | None = None, end_at: datetime | None = None,
                         page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
                         db: Session = Depends(get_db), _: User = Depends(current_user)):
    return _filtered_weather(db, variable, state, district, start_at, end_at, page, page_size)


@router.get("/observations/rainfall")
def rainfall_observations(state: str | None = None, district: str | None = None, start_at: datetime | None = None,
                          end_at: datetime | None = None, page: int = Query(1, ge=1),
                          page_size: int = Query(50, ge=1, le=500), db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(WeatherObservation).where(WeatherObservation.variable.ilike("%rain%"))
    query = _date_filters(query, WeatherObservation, start_at, end_at)
    query = _location_filter(query, WeatherObservation, state, district)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(WeatherObservation.observed_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_observation_out(row) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.get("/observations/rivers")
def river_observations(state: str | None = None, district: str | None = None, start_at: datetime | None = None,
                       end_at: datetime | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
                       db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(RiverObservation)
    query = _date_filters(query, RiverObservation, start_at, end_at)
    query = _location_filter(query, RiverObservation, state, district)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(RiverObservation.observed_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_observation_out(row) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.get("/historical/rainfall")
def historical_rainfall(state: str | None = None, district: str | None = None, start_at: datetime | None = None,
                        end_at: datetime | None = None, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
                        db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(HistoricalObservation).where(HistoricalObservation.variable.ilike("%rain%"))
    query = _date_filters(query, HistoricalObservation, start_at, end_at)
    query = _location_filter(query, HistoricalObservation, state, district)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(HistoricalObservation.observed_at).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_observation_out(row) | {"dataset_id": row.dataset_id, "coverage": row.coverage,
            "hazard_type": row.hazard_type} for row in rows], "page": page, "page_size": page_size, "total": total}


@router.get("/historical/disasters")
def historical_disasters(hazard_type: str | None = None, state: str | None = None, district: str | None = None,
                         start_at: datetime | None = None, end_at: datetime | None = None,
                         page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
                         db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(HistoricalObservation).where(HistoricalObservation.hazard_type.is_not(None))
    if hazard_type:
        query = query.where(HistoricalObservation.hazard_type == hazard_type)
    query = _date_filters(query, HistoricalObservation, start_at, end_at)
    query = _location_filter(query, HistoricalObservation, state, district)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(HistoricalObservation.observed_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_observation_out(row) | {"dataset_id": row.dataset_id, "hazard_type": row.hazard_type} for row in rows],
            "page": page, "page_size": page_size, "total": total}


@router.get("/map/layers")
def map_layers(state: str | None = None, district: str | None = None, hazard_type: str | None = None,
               severity: str | None = None, source_key: str | None = None, start_at: datetime | None = None, end_at: datetime | None = None,
               db: Session = Depends(get_db), _: User = Depends(current_user)):
    incidents = select(Incident)
    if state or district:
        incidents = _location_filter(incidents, Incident, state, district)
    if hazard_type:
        incidents = incidents.where(Incident.hazard_type == hazard_type)
    if severity:
        incidents = incidents.where(Incident.severity == severity)
    if source_key:
        incidents = incidents.join(DataSource, Incident.source_id == DataSource.id).where(DataSource.source_key == source_key)
    if start_at:
        incidents = incidents.where(Incident.source_published_at >= start_at)
    if end_at:
        incidents = incidents.where(Incident.source_published_at <= end_at)
    incident_rows = db.scalars(incidents.order_by(Incident.source_published_at.desc()).limit(1000)).all()
    weather_query = select(WeatherObservation)
    if state or district:
        weather_query = _location_filter(weather_query, WeatherObservation, state, district)
    if source_key:
        weather_query = weather_query.join(DataSource, WeatherObservation.source_id == DataSource.id).where(DataSource.source_key == source_key)
    if start_at:
        weather_query = weather_query.where(WeatherObservation.observed_at >= start_at)
    if end_at:
        weather_query = weather_query.where(WeatherObservation.observed_at <= end_at)
    weather_rows = db.scalars(weather_query.order_by(WeatherObservation.observed_at.desc()).limit(1000)).all()
    centers = db.scalars(select(ResourceCenter)).all()
    areas = db.scalars(select(AffectedArea)).all()
    return {"incidents": [_incident_out(row) for row in incident_rows], "weather": [_observation_out(row) for row in weather_rows],
            "resource_centers": [{"id": row.id, "name": row.name, "latitude": row.latitude, "longitude": row.longitude, "is_demo": row.is_demo} for row in centers],
            "affected_areas": [{"area_id": row.area_id, "name": row.name, "latitude": row.latitude, "longitude": row.longitude,
                "priority_class": row.priority_class, "priority_score": row.priority_score, "is_demo": bool(row.disaster and row.disaster.is_demo)} for row in areas]}


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db), _: User = Depends(current_user)):
    sources = db.scalars(select(DataSource)).all()
    sources_out = [_source_out(source) for source in sources]
    return {"mode": "mixed data platform; source-level provenance required", "official_warning_count": db.scalar(select(func.count(Incident.id)).where(Incident.is_official_warning.is_(True))) or 0,
            "incident_count": db.scalar(select(func.count(Incident.id)).where(Incident.is_official_warning.is_(False))) or 0,
            "weather_observation_count": db.scalar(select(func.count(WeatherObservation.id))) or 0,
            "river_observation_count": db.scalar(select(func.count(RiverObservation.id))) or 0,
            "historical_observation_count": db.scalar(select(func.count(HistoricalObservation.id))) or 0,
            "fresh_sources": sum(source["status"] == "Fresh" for source in sources_out), "sources": sources_out,
            "demo_data_present": db.scalar(select(func.count(AffectedArea.id)).where(AffectedArea.disaster_id.is_not(None))) > 0}


@router.get("/analytics/hazards")
def hazard_analytics(state: str | None = None, district: str | None = None, start_at: datetime | None = None,
                     end_at: datetime | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(Incident.hazard_type, Incident.severity, func.count(Incident.id)).group_by(Incident.hazard_type, Incident.severity)
    if state or district:
        query = _location_filter(query, Incident, state, district)
    if start_at:
        query = query.where(Incident.source_published_at >= start_at)
    if end_at:
        query = query.where(Incident.source_published_at <= end_at)
    return {"incidents_by_hazard_severity": [{"hazard_type": row[0], "severity": row[1], "count": row[2]} for row in db.execute(query).all()],
            "observations_by_source": [{"source_key": source.source_key, "count": count} for source, count in db.execute(
                select(DataSource, func.count(HistoricalObservation.id)).join(HistoricalObservation, HistoricalObservation.source_id == DataSource.id).group_by(DataSource.id)).all()],
            "data_note": "Aggregates only records ingested into Sahaaya; no synthetic incident data is included."}


def _decode_upload(filename: str, content: bytes) -> list[dict[str, Any]]:
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Upload exceeds 12 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Use a UTF-8 CSV or JSON file") from exc
    try:
        if filename.lower().endswith(".json"):
            decoded = json.loads(text)
            if isinstance(decoded, dict) and decoded.get("type") == "FeatureCollection":
                rows = []
                for feature in decoded.get("features", []):
                    if not isinstance(feature, dict):
                        rows.append({})
                        continue
                    row = dict(feature.get("properties") or {})
                    row.setdefault("id", feature.get("id"))
                    geometry = feature.get("geometry") or {}
                    coordinates = geometry.get("coordinates") or []
                    if geometry.get("type") == "Point" and len(coordinates) >= 2:
                        row.setdefault("longitude", coordinates[0])
                        row.setdefault("latitude", coordinates[1])
                    rows.append(row)
            else:
                rows = decoded
            if not isinstance(rows, list):
                raise ValueError("JSON must contain an array or GeoJSON FeatureCollection")
            return [row.get("properties", row) if isinstance(row, dict) else {} for row in rows]
        if filename.lower().endswith(".csv"):
            return list(csv.DictReader(io.StringIO(text)))
    except (json.JSONDecodeError, csv.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {exc}") from exc
    raise HTTPException(status_code=415, detail="Choose a .csv or .json file")


def _preview(rows: list[dict[str, Any]], mapping: HistoricalImportMapping):
    errors = []
    valid = []
    now = utcnow()
    for number, row in enumerate(rows, start=1):
        try:
            if mapping.timestamp_column not in row or mapping.value_column not in row:
                raise ValueError("mapped timestamp or value column is missing")
            timestamp = parse_datetime(row[mapping.timestamp_column])
            if timestamp is None:
                raise ValueError("timestamp could not be parsed")
            if timestamp > now:
                raise ValueError("future-dated row is not accepted as a measured historical observation")
            value = float(str(row[mapping.value_column]).replace(",", ""))
            if not math.isfinite(value):
                raise ValueError("numeric value must be finite")
            lat = lon = None
            if mapping.latitude_column and mapping.longitude_column:
                coords = validate_coordinates(row.get(mapping.latitude_column), row.get(mapping.longitude_column))
                if coords is None:
                    raise ValueError("coordinates are invalid")
                lat, lon = coords
            state_name = row.get(mapping.state_column) if mapping.state_column else None
            state_code = row.get(mapping.state_code_column) if mapping.state_code_column else None
            district_name = row.get(mapping.district_column) if mapping.district_column else None
            district_code = row.get(mapping.district_code_column) if mapping.district_code_column else None
            valid.append({"row_number": number, "external_record_id": str(row.get(mapping.id_column) or number) if mapping.id_column else str(number),
                          "observed_at": timestamp, "value": value, "unit": mapping.unit, "variable": mapping.variable,
                          "hazard_type": mapping.hazard_type, "location": row.get(mapping.location_column) if mapping.location_column else None,
                          "latitude": lat, "longitude": lon, "state_name": state_name, "state_code": state_code,
                          "district_name": district_name, "district_code": district_code, "raw": row})
        except (TypeError, ValueError, KeyError) as exc:
            errors.append({"row_number": number, "error": str(exc)})
    return valid, errors


async def _read_import(file: UploadFile, mapping_json: str):
    try:
        mapping = HistoricalImportMapping.model_validate_json(mapping_json)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc
    rows = _decode_upload(file.filename or "", await file.read())
    if not rows:
        raise HTTPException(status_code=422, detail="Dataset contains no records")
    valid, errors = _preview(rows, mapping)
    return rows, mapping, valid, errors


@router.post("/historical/import/preview")
async def historical_import_preview(file: UploadFile = File(...), mapping: str = Form(...), _: User = Depends(current_user)):
    rows, _, valid, errors = await _read_import(file, mapping)
    return {"total_rows": len(rows), "valid_rows": len(valid), "invalid_rows": len(errors),
            "preview": [{key: value for key, value in row.items() if key != "raw"} for row in valid[:20]],
            "errors": errors[:100], "future_records_rejected": sum("future-dated" in item["error"] for item in errors)}


@router.post("/historical/import")
async def historical_import(file: UploadFile = File(...), mapping: str = Form(...), dataset_id: str = Form(..., min_length=2, max_length=200),
                            publisher: str = Form(..., min_length=2, max_length=200), license_name: str = Form(..., min_length=2, max_length=240),
                            source_url: str | None = Form(None, max_length=1200),
                            coverage_start: datetime | None = Form(None), coverage_end: datetime | None = Form(None),
                            db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    if coverage_start and coverage_end and coverage_start > coverage_end:
        raise HTTPException(status_code=422, detail="Coverage start must be before coverage end")
    if source_url:
        source_parts = urlsplit(source_url)
        if source_parts.scheme != "https" or not source_parts.hostname or source_parts.username or source_parts.password:
            raise HTTPException(status_code=422, detail="Dataset source URL must be an HTTPS reference without embedded credentials")
    rows, mapping_obj, valid, errors = await _read_import(file, mapping)
    source = db.scalar(select(DataSource).where(DataSource.source_key == "historical_import"))
    if source is None:
        raise HTTPException(status_code=503, detail="Historical import source is not initialized")
    log = IngestionLog(source_id=source.id, status="completed", started_at=utcnow(), fetched_count=len(rows),
                       rejected_count=len(errors), details={"dataset_id": dataset_id, "publisher": publisher, "license": license_name})
    imported = duplicates = 0
    for row in valid:
        external = f"{dataset_id}:{row['external_record_id']}"
        packed = json.dumps(row["raw"], sort_keys=True, default=str, ensure_ascii=False)
        content_hash = hashlib.sha256(packed.encode()).hexdigest()
        raw = db.scalar(select(RawSourceRecord).where(RawSourceRecord.source_id == source.id,
            RawSourceRecord.external_record_id == external, RawSourceRecord.content_hash == content_hash))
        if raw:
            duplicates += 1
            continue
        revision = (db.scalar(select(func.max(RawSourceRecord.revision)).where(
            RawSourceRecord.source_id == source.id, RawSourceRecord.external_record_id == external)) or 0) + 1
        raw = RawSourceRecord(source_id=source.id, external_record_id=external, content_hash=content_hash,
            revision=revision, payload=row["raw"], source_published_at=row["observed_at"], fetched_at=utcnow(),
            source_url=source_url, quality_status="validated_import")
        db.add(raw)
        db.flush()
        existing = db.scalar(select(HistoricalObservation).where(HistoricalObservation.source_id == source.id,
            HistoricalObservation.dataset_id == dataset_id, HistoricalObservation.external_record_id == external,
            HistoricalObservation.variable == mapping_obj.variable, HistoricalObservation.observed_at == row["observed_at"]))
        location_id = None
        geo_source = "dataset:" + dataset_id
        parent_id = None
        state_code = str(row["state_code"] or row["state_name"] or "").strip() or None
        district_code = str(row["district_code"] or row["district_name"] or "").strip() or None
        for level, code, name in [("state", state_code, row["state_name"]), ("district", district_code, row["district_name"])]:
            if not code:
                continue
            geo = db.scalar(select(GeographicLocation).where(GeographicLocation.source == geo_source,
                GeographicLocation.external_code == f"{level}:{code}"))
            if geo is None:
                geo = GeographicLocation(source=geo_source, external_code=f"{level}:{code}", name=str(name or code), level=level,
                    parent_id=parent_id, country_code="IND", state_code=state_code, district_code=district_code, quality_status="unreviewed")
                db.add(geo)
                db.flush()
            parent_id = geo.id
        location_name = str(row["location"] or "").strip() or None
        if location_name or row["latitude"] is not None:
            external_location = location_name or f"{row['latitude']:.5f},{row['longitude']:.5f}"
            geo = db.scalar(select(GeographicLocation).where(GeographicLocation.source == geo_source,
                GeographicLocation.external_code == f"station:{external_location}"))
            if geo is None:
                geo = GeographicLocation(source=geo_source, external_code=f"station:{external_location}",
                    name=location_name or "Coordinate location", level="station", parent_id=parent_id,
                    country_code="IND", state_code=state_code, district_code=district_code,
                    latitude=row["latitude"], longitude=row["longitude"], quality_status="unreviewed")
                db.add(geo)
                db.flush()
            location_id = geo.id
        observation_values = {"raw_record_id": raw.id, "location_id": location_id, "hazard_type": mapping_obj.hazard_type,
            "value": row["value"], "unit": mapping_obj.unit, "latitude": row["latitude"], "longitude": row["longitude"],
            "location_name": location_name, "fetched_at": utcnow(), "coverage": {"publisher": publisher,
                "license": license_name, "source_url": source_url,
                "coverage_start": coverage_start.isoformat() if coverage_start else None,
                "coverage_end": coverage_end.isoformat() if coverage_end else None}, "quality_status": "imported"}
        if existing:
            for key, value in observation_values.items():
                setattr(existing, key, value)
        else:
            db.add(HistoricalObservation(source_id=source.id, dataset_id=dataset_id, external_record_id=external,
                variable=mapping_obj.variable, observed_at=row["observed_at"], **observation_values))
        imported += 1
    log.imported_count, log.duplicate_count, log.finished_at = imported, duplicates, utcnow()
    source.last_attempt_at = source.last_success_at = utcnow()
    source.latest_observation_at = max((item["observed_at"] for item in valid), default=source.latest_observation_at)
    source.last_record_count = imported
    source.status = "Fresh"
    db.add(log)
    db.commit()
    return {"dataset_id": dataset_id, "total_rows": len(rows), "imported": imported, "duplicates": duplicates,
            "rejected": len(errors), "errors": errors[:100], "human_review_required": True,
            "note": "Historical observations are stored separately from live weather and incident records."}


@router.post("/resources")
def create_resource_v1(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    # Preserve existing resource validation and behavior through the v0 endpoint.
    from .main import create_resource
    from .schemas import ResourceInput
    return create_resource(ResourceInput.model_validate(payload), db, user)
