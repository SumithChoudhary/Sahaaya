from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Timestamped, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="Emergency Officer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Disaster(Timestamped, Base):
    __tablename__ = "disasters"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="Demo scenario")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class AffectedArea(Timestamped, Base):
    __tablename__ = "affected_areas"
    id: Mapped[int] = mapped_column(primary_key=True)
    disaster_id: Mapped[int | None] = mapped_column(ForeignKey("disasters.id"), nullable=True)
    area_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    population_affected: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[int] = mapped_column(Integer, default=1)
    injured_people: Mapped[int] = mapped_column(Integer, default=0)
    trapped_people: Mapped[int] = mapped_column(Integer, default=0)
    emergency_requests: Mapped[int] = mapped_column(Integer, default=0)
    accessibility: Mapped[int] = mapped_column(Integer, default=3)
    distance_to_resource_center: Mapped[float] = mapped_column(Float, default=5)
    priority_score: Mapped[float] = mapped_column(Float, default=0)
    priority_class: Mapped[str] = mapped_column(String(20), default="Medium")
    status: Mapped[str] = mapped_column(String(30), default="Monitoring")
    disaster: Mapped[Disaster | None] = relationship()


class ResourceCenter(Timestamped, Base):
    __tablename__ = "resource_centers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class Resource(Timestamped, Base):
    __tablename__ = "resources"
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_key: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    total: Mapped[int] = mapped_column(Integer, default=0)
    available: Mapped[int] = mapped_column(Integer, default=0)
    allocated: Mapped[int] = mapped_column(Integer, default=0)
    deployed: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(40))
    center_id: Mapped[int | None] = mapped_column(ForeignKey("resource_centers.id"), nullable=True)
    center: Mapped[ResourceCenter | None] = relationship()


class ResourceInventory(Timestamped, Base):
    """Verified stock held at one center; separate from legacy aggregate resources."""
    __tablename__ = "resource_inventory"
    __table_args__ = (
        UniqueConstraint("center_id", "resource_key", name="uq_resource_inventory_center_key"),
        CheckConstraint("total >= 0 AND available >= 0 AND allocated >= 0 AND deployed >= 0", name="ck_inventory_nonnegative"),
        CheckConstraint("available + allocated + deployed <= total", name="ck_inventory_accounting"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    center_id: Mapped[int] = mapped_column(ForeignKey("resource_centers.id"), index=True)
    resource_key: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(120))
    total: Mapped[int] = mapped_column(Integer, default=0)
    available: Mapped[int] = mapped_column(Integer, default=0)
    allocated: Mapped[int] = mapped_column(Integer, default=0)
    deployed: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(40))
    quality_status: Mapped[str] = mapped_column(String(30), default="unverified")
    center: Mapped[ResourceCenter] = relationship()


class EmergencyRequest(Timestamped, Base):
    __tablename__ = "emergency_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("affected_areas.area_id"), index=True)
    request_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    people_affected: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="Pending")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    area: Mapped[AffectedArea] = relationship()


class Alert(Timestamped, Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    area_id: Mapped[str | None] = mapped_column(ForeignKey("affected_areas.area_id"), nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True, index=True)
    external_record_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[DataSource | None] = relationship()


class UserDisasterAlert(Timestamped, Base):
    """Operator-authored incident report; separate from verified external alerts."""
    __tablename__ = "user_disaster_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hazard_category: Mapped[str] = mapped_column(String(40), index=True)
    hazard_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), default="Open")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class DepartmentNotification(Timestamped, Base):
    __tablename__ = "department_notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("user_disaster_alerts.id", ondelete="CASCADE"), index=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResponseTask(Timestamped, Base):
    __tablename__ = "response_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("user_disaster_alerts.id", ondelete="CASCADE"), index=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="Assigned")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OptimizationRun(Timestamped, Base):
    __tablename__ = "optimization_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(30), default="completed")
    fitness: Mapped[float] = mapped_column(Float, default=0)
    generations: Mapped[int] = mapped_column(Integer, default=0)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Decision(Timestamped, Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("optimization_runs.id"), index=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("affected_areas.area_id"))
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    allocation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    run: Mapped[OptimizationRun] = relationship()
    area: Mapped[AffectedArea] = relationship()


class Deployment(Timestamped, Base):
    __tablename__ = "resource_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("optimization_runs.id"), nullable=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("affected_areas.area_id"), index=True)
    center_id: Mapped[int | None] = mapped_column(ForeignKey("resource_centers.id"), nullable=True, index=True)
    resource_key: Mapped[str] = mapped_column(String(60))
    required: Mapped[int] = mapped_column(Integer, default=0)
    allocated: Mapped[int] = mapped_column(Integer, default=0)
    deployed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="Approved")
    center: Mapped[ResourceCenter | None] = relationship()


class SimulationRun(Timestamped, Base):
    __tablename__ = "simulation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    parameters: Mapped[dict] = mapped_column(JSON)
    results: Mapped[dict] = mapped_column(JSON)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AuditEvent(Timestamped, Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    summary: Mapped[str] = mapped_column(String(240))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AppSetting(Timestamped, Base):
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    setting_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON)


class DataSource(Timestamped, Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    provider: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(60))
    endpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    license_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    license_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    freshness_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_credentials: Mapped[bool] = mapped_column(Boolean, default=False)
    credential_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="Not configured")
    etag: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_observation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_record_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Configuration here must contain non-secret settings only. Credentials stay in env vars.
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class IngestionLog(Timestamped, Base):
    __tablename__ = "ingestion_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[DataSource] = relationship()


class RawSourceRecord(Timestamped, Base):
    __tablename__ = "raw_source_records"
    __table_args__ = (UniqueConstraint("source_id", "external_record_id", "content_hash", name="uq_raw_source_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    external_record_id: Mapped[str] = mapped_column(String(240))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(30), default="unreviewed")
    source: Mapped[DataSource] = relationship()


class GeographicLocation(Timestamped, Base):
    __tablename__ = "geographic_locations"
    __table_args__ = (
        UniqueConstraint("source", "external_code", name="uq_geographic_source_code"),
        CheckConstraint("latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="ck_geographic_latitude"),
        CheckConstraint("longitude IS NULL OR (longitude >= -180 AND longitude <= 180)", name="ck_geographic_longitude"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("geographic_locations.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(80), default="manual")
    external_code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(180), index=True)
    level: Mapped[str] = mapped_column(String(40), index=True)  # country/state/district/subdistrict/locality/station
    country_code: Mapped[str] = mapped_column(String(3), default="IND")
    state_code: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    district_code: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(30), default="unreviewed")
    parent: Mapped[GeographicLocation | None] = relationship(remote_side="GeographicLocation.id")


class Incident(Timestamped, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("source_id", "external_record_id", name="uq_incident_source_external"),
        CheckConstraint("latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="ck_incident_latitude"),
        CheckConstraint("longitude IS NULL OR (longitude >= -180 AND longitude <= 180)", name="ck_incident_longitude"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    raw_record_id: Mapped[int | None] = mapped_column(ForeignKey("raw_source_records.id"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("geographic_locations.id"), nullable=True, index=True)
    external_record_id: Mapped[str] = mapped_column(String(240))
    hazard_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    magnitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(40), nullable=True)
    certainty: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="unreviewed")
    is_official_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    area_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[DataSource] = relationship()
    raw_record: Mapped[RawSourceRecord | None] = relationship()
    location: Mapped[GeographicLocation | None] = relationship()


class WeatherObservation(Timestamped, Base):
    __tablename__ = "weather_observations"
    __table_args__ = (UniqueConstraint("source_id", "external_record_id", "variable", "observed_at", name="uq_weather_observation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    raw_record_id: Mapped[int | None] = mapped_column(ForeignKey("raw_source_records.id"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("geographic_locations.id"), nullable=True, index=True)
    external_record_id: Mapped[str] = mapped_column(String(240))
    variable: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(30), default="unreviewed")
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[DataSource] = relationship()
    location: Mapped[GeographicLocation | None] = relationship()


class RiverObservation(Timestamped, Base):
    __tablename__ = "river_observations"
    __table_args__ = (UniqueConstraint("source_id", "external_record_id", "variable", "observed_at", name="uq_river_observation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    raw_record_id: Mapped[int | None] = mapped_column(ForeignKey("raw_source_records.id"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("geographic_locations.id"), nullable=True, index=True)
    external_record_id: Mapped[str] = mapped_column(String(240))
    river_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    variable: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(30), default="unreviewed")
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[DataSource] = relationship()
    location: Mapped[GeographicLocation | None] = relationship()


class HistoricalObservation(Timestamped, Base):
    __tablename__ = "historical_observations"
    __table_args__ = (UniqueConstraint("source_id", "external_record_id", "variable", "observed_at", name="uq_historical_observation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    raw_record_id: Mapped[int | None] = mapped_column(ForeignKey("raw_source_records.id"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("geographic_locations.id"), nullable=True, index=True)
    dataset_id: Mapped[str] = mapped_column(String(200), index=True)
    external_record_id: Mapped[str] = mapped_column(String(240))
    hazard_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    variable: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_status: Mapped[str] = mapped_column(String(30), default="unreviewed")
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[DataSource] = relationship()
    location: Mapped[GeographicLocation | None] = relationship()


class PriorityAssessment(Timestamped, Base):
    __tablename__ = "priority_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("affected_areas.area_id"), index=True)
    priority_score: Mapped[float] = mapped_column(Float)
    priority_class: Mapped[str] = mapped_column(String(20), index=True)
    model_version: Mapped[str] = mapped_column(String(100))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    input_features: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_status: Mapped[str] = mapped_column(String(30), default="unreviewed")


class DeploymentAudit(Timestamped, Base):
    __tablename__ = "deployment_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("resource_allocations.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
