from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
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
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
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
    resource_key: Mapped[str] = mapped_column(String(60))
    required: Mapped[int] = mapped_column(Integer, default=0)
    allocated: Mapped[int] = mapped_column(Integer, default=0)
    deployed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="Approved")


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
