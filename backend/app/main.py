from __future__ import annotations

import csv
import io
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine, get_db
from .models import (
    AffectedArea, Alert, AppSetting, AuditEvent, Decision, Deployment, Disaster,
    EmergencyRequest, OptimizationRun, Resource, ResourceCenter, SimulationRun, User,
)
from .schemas import (
    AlertUpdate, AllocationChange, AreaCreate, AreaUpdate, CenterInput,
    DeploymentUpdate, GAParameters, LoginRequest, OptimizationInput,
    RejectInput, RequestInput, RequestUpdate, ResourceInput, ResourceUpdate,
    ScenarioInput, SettingsInput, TokenOut,
)
from .security import create_access_token, current_user, hash_password, require_roles, verify_password
from .services.demand import demand_table, estimate_area_demand
from .services.optimizer import optimize
from .services.priority import predict_priority


def log_event(db: Session, category: str, summary: str, details: dict | None = None, user_id: int | None = None) -> None:
    db.add(AuditEvent(category=category, summary=summary, details=details or {}, user_id=user_id))


def add_alert(db: Session, severity: str, title: str, message: str, area_id: str | None = None) -> None:
    db.add(Alert(alert_id=f"AL-{secrets.token_hex(4).upper()}", severity=severity, title=title, message=message, area_id=area_id, is_read=False))


def area_payload(area: AffectedArea) -> dict:
    return {
        "id": area.id, "area_id": area.area_id, "name": area.name,
        "latitude": area.latitude, "longitude": area.longitude,
        "population_affected": area.population_affected, "severity": area.severity,
        "injured_people": area.injured_people, "trapped_people": area.trapped_people,
        "emergency_requests": area.emergency_requests, "accessibility": area.accessibility,
        "distance_to_resource_center": area.distance_to_resource_center,
        "priority_score": area.priority_score, "priority_class": area.priority_class,
        "status": area.status, "created_at": area.created_at, "updated_at": area.updated_at,
    }


def resource_payload(resource: Resource) -> dict:
    return {
        "id": resource.id, "resource_key": resource.resource_key, "name": resource.name,
        "total": resource.total, "available": resource.available, "allocated": resource.allocated,
        "deployed": resource.deployed, "remaining": max(resource.total-resource.deployed, 0),
        "unit": resource.unit, "center_id": resource.center_id,
        "center_name": resource.center.name if resource.center else None,
        "status": "Available" if resource.available > 0 else "Depleted",
        "created_at": resource.created_at, "updated_at": resource.updated_at,
    }


def request_payload(item: EmergencyRequest) -> dict:
    return {
        "id": item.id, "request_id": item.request_id, "area_id": item.area_id,
        "area_name": item.area.name if item.area else None, "request_type": item.request_type,
        "severity": item.severity, "people_affected": item.people_affected,
        "status": item.status, "timestamp": item.timestamp,
    }


def _migrate_legacy_demo_identity(db: Session) -> None:
    """Keep existing local demo accounts usable after the public rebrand."""
    legacy_accounts = {
        "sumith@resqai.demo": ("sumith@sahaaya.demo", "Sumith Choudhary"),
        "admin@resqai.demo": ("admin@sahaaya.demo", "Sahaaya Administrator"),
        "viewer@resqai.demo": ("viewer@sahaaya.demo", "Sahaaya Viewer"),
    }
    for legacy_email, (new_email, display_name) in legacy_accounts.items():
        user = db.scalar(select(User).where(User.email == legacy_email))
        if user is None:
            continue
        existing = db.scalar(select(User).where(User.email == new_email))
        if existing is None:
            user.email = new_email
        if user.name in {"ResQAI Administrator", "ResQAI Viewer"}:
            user.name = display_name
    db.commit()


def _seed_if_empty(db: Session) -> None:
    if db.scalar(select(func.count(User.id))) == 0:
        email = os.getenv("DEMO_USER_EMAIL", "sumith@sahaaya.demo")
        password = os.getenv("DEMO_USER_PASSWORD", "demo-preview")
        db.add_all([
            User(name=os.getenv("DEMO_USER_NAME", "Sumith Choudhary"), email=email, password_hash=hash_password(password), role="Emergency Officer"),
            User(name="Sahaaya Administrator", email="admin@sahaaya.demo", password_hash=hash_password(os.getenv("DEMO_ADMIN_PASSWORD", "demo-admin-preview")), role="Administrator"),
            User(name="Sahaaya Viewer", email="viewer@sahaaya.demo", password_hash=hash_password(os.getenv("DEMO_VIEWER_PASSWORD", "demo-viewer-preview")), role="Viewer"),
        ])
    if db.scalar(select(func.count(Disaster.id))) == 0:
        disaster = Disaster(name="Monsoon response · demo environment", status="Demo scenario", is_demo=True)
        db.add(disaster)
        db.flush()
        from .seed import AREAS, CENTERS, REQUESTS, RESOURCES, ALERTS
        db.add_all([AffectedArea(disaster_id=disaster.id, **area) for area in AREAS])
        db.add_all([ResourceCenter(**center) for center in CENTERS])
        db.flush()
        centers = {center.name: center.id for center in db.scalars(select(ResourceCenter)).all()}
        db.add_all([Resource(center_id=centers.get(item["center_name"]), **{key: value for key, value in item.items() if key != "center_name"}) for item in RESOURCES])
        db.flush()
        db.add_all([EmergencyRequest(**request) for request in REQUESTS])
        db.add_all([Alert(**alert) for alert in ALERTS])
        db.add_all([
            AppSetting(setting_key="optimization", value={"population_size":80,"generations":100,"mutation_rate":0.08,"crossover_rate":0.8}),
            AppSetting(setting_key="priority_thresholds", value={"critical":80,"high":60}),
            AppSetting(setting_key="preferences", value={"timezone":"Asia/Kolkata","date_format":"DD MMM YYYY","notifications":True}),
        ])
        db.commit()
    db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _migrate_legacy_demo_identity(db)
        _seed_if_empty(db)
    yield


app = FastAPI(title="Sahaaya Decision Support API", version="1.0.0", description="Human-reviewed disaster resource decision support. Demo inputs are fictional; no automatic dispatch.", lifespan=lifespan)
origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
        return {"status": "ok", "database": "connected", "mode": "fictional demo environment"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc


@app.post("/api/auth/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return {"access_token": create_access_token(user), "user": user}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


@app.get("/api/areas")
def list_areas(q: str = "", priority: str | None = None, sort: str = "area_id", direction: str = "asc", db: Session = Depends(get_db), _: User = Depends(current_user)):
    allowed = {"area_id", "name", "population_affected", "severity", "priority_score", "emergency_requests"}
    if sort not in allowed:
        sort = "area_id"
    column = getattr(AffectedArea, sort)
    statement = select(AffectedArea)
    if q:
        statement = statement.where((AffectedArea.name.ilike(f"%{q}%")) | (AffectedArea.area_id.ilike(f"%{q}%")))
    if priority:
        statement = statement.where(AffectedArea.priority_class == priority)
    statement = statement.order_by(column.desc() if direction == "desc" else column.asc())
    return [area_payload(area) for area in db.scalars(statement).all()]


@app.post("/api/areas", status_code=201)
def create_area(payload: AreaCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    if db.scalar(select(AffectedArea).where(AffectedArea.area_id == payload.area_id)):
        raise HTTPException(status_code=409, detail="Area ID already exists")
    area = AffectedArea(**payload.model_dump())
    prediction = predict_priority(payload.model_dump())
    area.priority_score = prediction["priority_score"]
    area.priority_class = prediction["priority_class"]
    db.add(area)
    log_event(db, "area.created", f"Created affected area {area.area_id}", {"area_id": area.area_id}, user.id)
    db.commit()
    db.refresh(area)
    return area_payload(area)


@app.post("/api/areas/import", status_code=201)
async def import_areas(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Choose a .csv file")
    try:
        contents = (await file.read()).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(contents))
        required = set(AreaCreate.model_fields)
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise HTTPException(status_code=422, detail=f"CSV columns required: {', '.join(sorted(required))}")
        records = []
        existing_ids = {value for (value,) in db.execute(select(AffectedArea.area_id)).all()}
        seen = set()
        for line, row in enumerate(reader, start=2):
            try:
                item = AreaCreate.model_validate(row)
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"Invalid row {line}: {exc}") from exc
            if item.area_id in existing_ids or item.area_id in seen:
                raise HTTPException(status_code=409, detail=f"Duplicate area_id on row {line}: {item.area_id}")
            seen.add(item.area_id)
            payload = item.model_dump()
            prediction = predict_priority(payload)
            records.append(AffectedArea(**payload, priority_score=prediction["priority_score"], priority_class=prediction["priority_class"]))
        if not records:
            raise HTTPException(status_code=422, detail="CSV contains no area rows")
        db.add_all(records)
        log_event(db, "area.imported", f"Imported {len(records)} affected areas from CSV", {"area_ids": [item.area_id for item in records]}, user.id)
        db.commit()
        return {"imported": len(records), "areas": [area_payload(item) for item in records]}
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV must use UTF-8 encoding") from exc


@app.get("/api/areas/{area_id}")
def get_area(area_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    area = db.scalar(select(AffectedArea).where(AffectedArea.area_id == area_id))
    if area is None:
        raise HTTPException(status_code=404, detail="Affected area not found")
    return area_payload(area)


@app.put("/api/areas/{area_id}")
def update_area(area_id: str, payload: AreaUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    area = db.scalar(select(AffectedArea).where(AffectedArea.area_id == area_id))
    if area is None:
        raise HTTPException(status_code=404, detail="Affected area not found")
    before = {key: getattr(area, key) for key in payload.model_dump(exclude_none=True)}
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(area, key, value)
    if area.injured_people > area.population_affected or area.trapped_people > area.population_affected:
        raise HTTPException(status_code=422, detail="Injured and trapped counts cannot exceed the affected population")
    priority_fields = {"population_affected", "severity", "injured_people", "trapped_people", "emergency_requests", "accessibility", "distance_to_resource_center"}
    if priority_fields.intersection(payload.model_fields_set):
        prediction = predict_priority(area_payload(area))
        area.priority_score, area.priority_class = prediction["priority_score"], prediction["priority_class"]
        log_event(db, "priority.changed", f"Recalculated demo priority for {area.name}", {"area_id": area.area_id, "before": before, "score": area.priority_score, "priority": area.priority_class}, user.id)
        previous_score = before.get("priority_score", 0)
        if area.priority_score > previous_score + 5:
            add_alert(db, "Warning", "Demo priority score increased", f"{area.name} priority changed to {area.priority_class} ({area.priority_score:.0f}). Review updated inputs.", area.area_id)
        if area.priority_class == "Critical" and before.get("priority_class") != "Critical":
            add_alert(db, "Critical", "Critical demo area detected", f"{area.name} received a Critical synthetic demo priority. Human review required.", area.area_id)
    log_event(db, "area.updated", f"Updated affected area {area.area_id}", {"area_id": area.area_id, "changed": list(payload.model_fields_set)}, user.id)
    db.commit()
    db.refresh(area)
    return area_payload(area)


@app.delete("/api/areas/{area_id}", status_code=204)
def delete_area(area_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    area = db.scalar(select(AffectedArea).where(AffectedArea.area_id == area_id))
    if area is None:
        raise HTTPException(status_code=404, detail="Affected area not found")
    if db.scalar(select(EmergencyRequest).where(EmergencyRequest.area_id == area_id)) or db.scalar(select(Decision).where(Decision.area_id == area_id)):
        raise HTTPException(status_code=409, detail="Area has requests or decisions. Archive it by changing its status instead.")
    db.delete(area)
    log_event(db, "area.deleted", f"Deleted affected area {area_id}", {"area_id": area_id}, user.id)
    db.commit()
    return Response(status_code=204)


@app.get("/api/resources")
def list_resources(q: str = "", db: Session = Depends(get_db), _: User = Depends(current_user)):
    statement = select(Resource).order_by(Resource.name)
    if q:
        statement = statement.where(Resource.name.ilike(f"%{q}%") | Resource.resource_key.ilike(f"%{q}%"))
    return [resource_payload(item) for item in db.scalars(statement).all()]


@app.post("/api/resources", status_code=201)
def create_resource(payload: ResourceInput, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    if payload.available + payload.allocated + payload.deployed > payload.total:
        raise HTTPException(status_code=422, detail="Available, allocated, and deployed quantities cannot exceed total")
    item = Resource(**payload.model_dump())
    db.add(item)
    log_event(db, "resource.created", f"Added resource {payload.name}", {"resource_key": payload.resource_key}, user.id)
    db.commit()
    db.refresh(item)
    return resource_payload(item)


@app.put("/api/resources/{resource_key}")
def update_resource(resource_key: str, payload: ResourceUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    item = db.scalar(select(Resource).where(Resource.resource_key == resource_key))
    if item is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    values = payload.model_dump(exclude_unset=True)
    quantities = {key: values.get(key, getattr(item, key)) for key in ("total", "available", "allocated", "deployed")}
    if quantities["available"] + quantities["allocated"] + quantities["deployed"] > quantities["total"]:
        raise HTTPException(status_code=422, detail="Available, allocated, and deployed quantities cannot exceed total")
    previous_available = item.available
    for key, value in values.items():
        setattr(item, key, value)
    if item.available < previous_available and item.total > 0 and item.available / item.total < 0.6:
        add_alert(db, "Warning", "Resource shortage threshold", f"{item.name} availability is below 60% of demo inventory.")
    log_event(db, "resource.updated", f"Updated resource {item.name}", {"resource_key": item.resource_key, "changed": list(values)}, user.id)
    db.commit()
    db.refresh(item)
    return resource_payload(item)


@app.get("/api/resource-centers")
def list_centers(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [{"id": item.id, "name": item.name, "latitude": item.latitude, "longitude": item.longitude, "is_demo": item.is_demo} for item in db.scalars(select(ResourceCenter).order_by(ResourceCenter.name)).all()]


@app.post("/api/resource-centers", status_code=201)
def create_center(payload: CenterInput, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    center = ResourceCenter(**payload.model_dump(), is_demo=True)
    db.add(center)
    log_event(db, "resource_center.created", f"Added resource center {center.name}", payload.model_dump(), user.id)
    db.commit()
    db.refresh(center)
    return {"id": center.id, "name": center.name, "latitude": center.latitude, "longitude": center.longitude, "is_demo": True}


@app.get("/api/requests")
def list_requests(status: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    statement = select(EmergencyRequest).order_by(EmergencyRequest.timestamp.desc())
    if status:
        statement = statement.where(EmergencyRequest.status == status)
    return [request_payload(item) for item in db.scalars(statement).all()]


@app.post("/api/requests", status_code=201)
def create_request(payload: RequestInput, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    if db.scalar(select(AffectedArea).where(AffectedArea.area_id == payload.area_id)) is None:
        raise HTTPException(status_code=404, detail="Affected area not found")
    request_id = f"RQ-{secrets.token_hex(4).upper()}"
    item = EmergencyRequest(request_id=request_id, **payload.model_dump())
    db.add(item)
    log_event(db, "request.created", f"New {payload.request_type.lower()} request for {payload.area_id}", {"request_id": request_id}, user.id)
    if payload.severity in ("Critical", "High"):
        add_alert(db, "Warning" if payload.severity == "High" else "Critical", "New emergency request", f"{payload.severity} {payload.request_type.lower()} request recorded for {payload.area_id} in the demo scenario.", payload.area_id)
    db.commit()
    db.refresh(item)
    return request_payload(item)


@app.patch("/api/requests/{request_id}")
def update_request(request_id: str, payload: RequestUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    item = db.scalar(select(EmergencyRequest).where(EmergencyRequest.request_id == request_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Emergency request not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    log_event(db, "request.updated", f"Updated emergency request {request_id}", payload.model_dump(exclude_unset=True), user.id)
    db.commit()
    db.refresh(item)
    return request_payload(item)


def _area_feature(area: AffectedArea) -> dict:
    return {"population_affected": area.population_affected, "severity": area.severity, "emergency_requests": area.emergency_requests, "injured_people": area.injured_people, "trapped_people": area.trapped_people, "accessibility": area.accessibility, "distance_to_resource_center": area.distance_to_resource_center}


@app.post("/api/ml/priority")
def priority_prediction(payload: dict, _: User = Depends(current_user)):
    required = ["population_affected", "severity", "emergency_requests", "injured_people", "trapped_people", "accessibility", "distance_to_resource_center"]
    if not all(key in payload for key in required):
        raise HTTPException(status_code=422, detail=f"Required fields: {', '.join(required)}")
    try:
        return predict_priority(payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Demo priority model could not produce a prediction") from exc


@app.post("/api/resources/estimate-demand")
def estimate_demand(payload: dict | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    if payload and "area_id" in payload:
        area = db.scalar(select(AffectedArea).where(AffectedArea.area_id == payload["area_id"]))
        if area is None:
            raise HTTPException(status_code=404, detail="Affected area not found")
        return {"area_id": area.area_id, "demand": estimate_area_demand(_area_feature(area)), "status": "Transparent prototype heuristic · replace with validated demand model"}
    area_rows = [area_payload(area) for area in db.scalars(select(AffectedArea)).all()]
    resource_rows = [resource_payload(resource) for resource in db.scalars(select(Resource)).all()]
    return {"areas": demand_table(area_rows, resource_rows), "status": "Transparent prototype heuristic · replace with validated demand model"}


@app.post("/api/areas/recalculate-priorities")
def recalculate_priorities(db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    results = []
    for area in db.scalars(select(AffectedArea)).all():
        prediction = predict_priority(_area_feature(area))
        before = {"priority_score": area.priority_score, "priority_class": area.priority_class}
        area.priority_score, area.priority_class = prediction["priority_score"], prediction["priority_class"]
        results.append({"area_id": area.area_id, "before": before, "after": {"priority_score": area.priority_score, "priority_class": area.priority_class}})
    log_event(db, "priority.recalculated", "Recalculated demo priorities", {"areas": len(results)}, user.id)
    db.commit()
    return {"results": results, "model_status": "Synthetic demo model · not validated on real disaster outcomes"}


def _optimization_inputs(db: Session, area_ids: list[str] | None):
    statement = select(AffectedArea).order_by(AffectedArea.area_id)
    if area_ids:
        statement = statement.where(AffectedArea.area_id.in_(area_ids))
    area_objects = db.scalars(statement).all()
    if not area_objects:
        raise HTTPException(status_code=422, detail="No affected areas selected")
    areas = [area_payload(area) for area in area_objects]
    resource_objects = db.scalars(select(Resource)).all()
    resources = [{"resource_key": item.resource_key, "available": item.available, "total": item.total} for item in resource_objects]
    centers = [{"id": item.id, "latitude": item.latitude, "longitude": item.longitude} for item in db.scalars(select(ResourceCenter)).all()]
    demands = demand_table(areas, resources)
    return area_objects, areas, resource_objects, centers, demands


@app.post("/api/optimization/run", status_code=201)
def run_optimization(payload: OptimizationInput, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    area_objects, areas, resources, centers, demands = _optimization_inputs(db, payload.area_ids)
    params = payload.parameters.model_dump()
    try:
        result = optimize(areas, demands, [resource_payload(item) for item in resources], centers, params)
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    run = OptimizationRun(status="pending_review", fitness=result["best_fitness"], generations=result["generation"], parameters=params, results=result, created_by=user.id)
    db.add(run)
    log_event(db, "optimization.completed", "Custom Genetic Algorithm completed; pending human review", {"fitness": result["best_fitness"], "areas": len(area_objects)}, user.id)
    add_alert(db, "Success", "Optimization completed", f"Run #{run.id} generated a recommendation set pending authority review.")
    db.commit()
    db.refresh(run)
    return {"id": run.id, **result, "status": run.status, "created_at": run.created_at}


@app.get("/api/optimization")
def list_optimizations(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [{"id": item.id, "status": item.status, "fitness": item.fitness, "generations": item.generations, "parameters": item.parameters, "created_at": item.created_at} for item in db.scalars(select(OptimizationRun).order_by(OptimizationRun.created_at.desc())).all()]


@app.get("/api/optimization/{run_id}")
def get_optimization(run_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    item = db.get(OptimizationRun, run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Optimization run not found")
    decisions = db.scalars(select(Decision).where(Decision.run_id == run_id)).all()
    return {"id": item.id, **item.results, "status": item.status, "created_at": item.created_at, "decisions": [{"id": d.id, "area_id": d.area_id, "decision": d.decision, "reason": d.reason, "allocation": d.allocation} for d in decisions]}


def _review(run_id: int, area_id: str, action: str, reason: str | None, allocation: dict | None, db: Session, user: User):
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Optimization run not found")
    row = next((item for item in run.results.get("results", []) if item["area_id"] == area_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Area is not part of this run")
    if action == "Modified":
        if allocation is None:
            raise HTTPException(status_code=422, detail="Modified allocation is required")
        available = {item.resource_key: item.available for item in db.scalars(select(Resource)).all()}
        for key, count in allocation.items():
            if key not in row["required"] or not isinstance(count, int) or count < 0:
                raise HTTPException(status_code=422, detail=f"Invalid allocation for {key}")
            if count > row["required"][key]:
                raise HTTPException(status_code=422, detail=f"Allocation for {key} exceeds estimated area demand")
            if count > available.get(key, 0):
                raise HTTPException(status_code=422, detail=f"Allocation for {key} exceeds available supply")
            other_proposals = sum(entry["allocated"].get(key, 0) for entry in run.results.get("results", []) if entry["area_id"] != area_id)
            if count + other_proposals > available.get(key, 0):
                raise HTTPException(status_code=422, detail=f"Modified allocation for {key} would exceed supply proposed for other areas")
        row["allocated"] = {**row["allocated"], **allocation}
        row["unmet"] = {key: max(row["required"].get(key, 0)-row["allocated"].get(key, 0), 0) for key in row["required"]}
        run.results = {**run.results, "results": [row if entry["area_id"] == area_id else entry for entry in run.results["results"]]}
    if action in ("Approved", "Modified"):
        available = {item.resource_key: item.available for item in db.scalars(select(Resource)).all()}
        prior_approvals = db.scalars(select(Deployment).where(Deployment.run_id == run_id, Deployment.area_id != area_id)).all()
        committed = {}
        for item in prior_approvals:
            committed[item.resource_key] = committed.get(item.resource_key, 0) + item.allocated
        for key, count in row["allocated"].items():
            if count + committed.get(key, 0) > available.get(key, 0):
                raise HTTPException(status_code=422, detail=f"Approval for {key} exceeds currently available supply")
    decision = Decision(run_id=run_id, area_id=area_id, decision=action, reason=reason, allocation=allocation, user_id=user.id)
    db.add(decision)
    if action in ("Approved", "Modified"):
        approved = row["allocated"]
        for resource_key, count in approved.items():
            existing = db.scalar(select(Deployment).where(Deployment.run_id == run_id, Deployment.area_id == area_id, Deployment.resource_key == resource_key))
            if existing:
                existing.allocated = count
            else:
                db.add(Deployment(run_id=run_id, area_id=area_id, resource_key=resource_key, required=row["required"].get(resource_key, 0), allocated=count, status="Approved"))
    reviewed_ids = set(db.scalars(select(Decision.area_id).where(Decision.run_id == run_id)).all()) | {area_id}
    run.status = "reviewed" if len(reviewed_ids) >= len(run.results.get("results", [])) else "pending_review"
    log_event(db, f"decision.{action.lower()}", f"{action} recommendation for {area_id}", {"run_id": run_id, "reason": reason}, user.id)
    if action == "Modified":
        add_alert(db, "Info", "Allocation modified by officer", f"The proposed allocation for {area_id} was changed by an authority.", area_id)
    db.commit()
    db.refresh(decision)
    return {"id": decision.id, "run_id": run_id, "area_id": area_id, "decision": action, "reason": reason, "allocation": allocation, "created_at": decision.created_at, "human_authority": user.name, "automatic_dispatch": False}


@app.post("/api/optimization/{run_id}/approve")
def approve(run_id: int, payload: AllocationChange, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    return _review(run_id, payload.area_id, "Approved", payload.reason, None, db, user)


@app.post("/api/optimization/{run_id}/modify")
def modify(run_id: int, payload: AllocationChange, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    return _review(run_id, payload.area_id, "Modified", payload.reason, payload.allocation, db, user)


@app.post("/api/optimization/{run_id}/reject")
def reject(run_id: int, payload: RejectInput, area_id: str = Query(...), db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    return _review(run_id, area_id, "Rejected", payload.reason, None, db, user)


@app.get("/api/deployments")
def list_deployments(db: Session = Depends(get_db), _: User = Depends(current_user)):
    areas = {area.area_id: area.name for area in db.scalars(select(AffectedArea)).all()}
    return [{"id": item.id, "run_id": item.run_id, "area_id": item.area_id, "area_name": areas.get(item.area_id), "resource_key": item.resource_key, "required": item.required, "allocated": item.allocated, "deployed": item.deployed, "remaining": item.allocated-item.deployed, "status": item.status, "updated_at": item.updated_at} for item in db.scalars(select(Deployment).order_by(Deployment.updated_at.desc())).all()]


@app.patch("/api/deployments/{deployment_id}")
def update_deployment(deployment_id: int, payload: DeploymentUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    item = db.get(Deployment, deployment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Deployment record not found")
    if payload.deployed > item.allocated:
        raise HTTPException(status_code=422, detail="Deployed quantity cannot exceed approved allocation")
    item.deployed, item.status = payload.deployed, payload.status
    log_event(db, "deployment.updated", f"Updated manual deployment for {item.area_id}", payload.model_dump(), user.id)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "area_id": item.area_id, "resource_key": item.resource_key, "allocated": item.allocated, "deployed": item.deployed, "remaining": item.allocated-item.deployed, "status": item.status}


@app.get("/api/alerts")
def list_alerts(unread: bool | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    statement = select(Alert).order_by(Alert.timestamp.desc())
    if unread is not None:
        statement = statement.where(Alert.is_read == (not unread))
    return [{"id": item.id, "alert_id": item.alert_id, "severity": item.severity, "title": item.title, "message": item.message, "area_id": item.area_id, "is_read": item.is_read, "timestamp": item.timestamp} for item in db.scalars(statement).all()]


@app.patch("/api/alerts/{alert_id}")
def update_alert(alert_id: str, payload: AlertUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    item = db.scalar(select(Alert).where(Alert.alert_id == alert_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    item.is_read = payload.is_read
    log_event(db, "alert.updated", f"Marked alert {alert_id} {'read' if payload.is_read else 'unread'}", {}, user.id)
    db.commit()
    return {"alert_id": alert_id, "is_read": item.is_read}


@app.get("/api/analytics/overview")
def analytics_overview(db: Session = Depends(get_db), _: User = Depends(current_user)):
    areas = [area_payload(item) for item in db.scalars(select(AffectedArea)).all()]
    resources = [resource_payload(item) for item in db.scalars(select(Resource)).all()]
    requests = [request_payload(item) for item in db.scalars(select(EmergencyRequest)).all()]
    demand = demand_table(areas, resources)
    runs = db.scalars(select(OptimizationRun).order_by(OptimizationRun.created_at.desc()).limit(12)).all()
    priority = {name: sum(1 for area in areas if area["priority_class"] == name) for name in ("Critical", "High", "Medium", "Low")}
    return {
        "areas": areas,
        "requests": requests,
        "priority_distribution": [{"name": key, "count": value} for key, value in priority.items()],
        "resource_utilization": [{"resource": item["name"], "available": item["available"], "allocated": item["allocated"], "deployed": item["deployed"], "total": item["total"]} for item in resources],
        "demand_vs_available": [{"area_id": row["area_id"], "area_name": row["area_name"], "demand": sum(row["estimated_demand"].values()), "available": sum(row["available_resources"].values()), "unmet": sum(row["unmet_demand"].values())} for row in demand],
        "ga_convergence": [{"run_id": run.id, "fitness_history": run.results.get("fitness_history", []), "created_at": run.created_at} for run in runs],
        "model_status": "Synthetic demo priority model; no real-world validation",
    }


@app.post("/api/simulation/run", status_code=201)
def run_simulation(payload: ScenarioInput, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator", "Emergency Officer"))):
    area_objects, baseline_areas, resource_objects, centers, _ = _optimization_inputs(db, None)
    baseline_resources = [resource_payload(item) for item in resource_objects]
    params_row = db.scalar(select(AppSetting).where(AppSetting.setting_key == "optimization"))
    params = GAParameters(**(params_row.value if params_row else {})).model_dump()
    baseline_demand = demand_table(baseline_areas, baseline_resources)
    baseline = optimize(baseline_areas, baseline_demand, baseline_resources, centers, params)
    scenario_areas = []
    for area in baseline_areas:
        changed = area.copy()
        changed["population_affected"] = max(round(changed["population_affected"] * (1 + payload.population_change_pct / 100)), 0)
        changed["severity"] = min(5, max(1, round(changed["severity"] * (1 + payload.severity_change_pct / 100))))
        changed["emergency_requests"] = max(round(changed["emergency_requests"] * (1 + payload.request_change_pct / 100)), 0)
        priority = predict_priority(changed)
        changed["priority_score"], changed["priority_class"] = priority["priority_score"], priority["priority_class"]
        scenario_areas.append(changed)
    scenario_resources = []
    for item in baseline_resources:
        changed = item.copy()
        pct = payload.ambulance_availability_pct if item["resource_key"] == "ambulances" else payload.rescue_availability_pct if item["resource_key"] == "rescue-teams" else payload.medical_availability_pct if item["resource_key"] == "medical-kits" else 0
        changed["available"] = max(round(changed["available"] * (1 + pct / 100)), 0)
        scenario_resources.append(changed)
    scenario_demand = demand_table(scenario_areas, scenario_resources)
    scenario = optimize(scenario_areas, scenario_demand, scenario_resources, centers, params)
    comparison = {"baseline": {"before": baseline["after"], "demand": baseline["total_demand"], "allocated": baseline["total_allocated"], "unmet": baseline["after"]["total_unmet_demand"], "resource_utilization": baseline["after"]["resource_utilization"]}, "scenario": {"before": scenario["after"], "demand": scenario["total_demand"], "allocated": scenario["total_allocated"], "unmet": scenario["after"]["total_unmet_demand"], "resource_utilization": scenario["after"]["resource_utilization"], "areas": scenario["results"]}}
    record = SimulationRun(name="What-if demo scenario", parameters=payload.model_dump(), results=comparison, user_id=user.id)
    db.add(record)
    log_event(db, "simulation.completed", "Compared baseline and what-if demo scenario", payload.model_dump(), user.id)
    db.commit()
    db.refresh(record)
    return {"id": record.id, **comparison, "notice": "Both scenarios use simulated data and the prototype Genetic Algorithm."}


@app.get("/api/simulation")
def list_simulations(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [{"id": item.id, "name": item.name, "parameters": item.parameters, "results": item.results, "created_at": item.created_at} for item in db.scalars(select(SimulationRun).order_by(SimulationRun.created_at.desc())).all()]


@app.get("/api/history")
def history(limit: int = Query(default=100, ge=1, le=500), category: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    statement = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if category:
        statement = select(AuditEvent).where(AuditEvent.category == category).order_by(AuditEvent.created_at.desc()).limit(limit)
    return [{"id": item.id, "category": item.category, "summary": item.summary, "details": item.details, "user_id": item.user_id, "created_at": item.created_at} for item in db.scalars(statement).all()]


@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return {item.setting_key: item.value for item in db.scalars(select(AppSetting)).all()}


@app.put("/api/settings/{key}")
def update_settings(key: str, payload: SettingsInput, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator"))):
    if key not in ("optimization", "priority_thresholds"):
        raise HTTPException(status_code=404, detail="Setting key is not editable")
    item = db.scalar(select(AppSetting).where(AppSetting.setting_key == key))
    if item is None:
        item = AppSetting(setting_key=key, value=payload.model_dump())
        db.add(item)
    else:
        item.value = payload.model_dump()
    log_event(db, "settings.updated", f"Updated {key} settings", payload.model_dump(), user.id)
    db.commit()
    return {"key": key, "value": item.value}


@app.get("/api/reports/{report_type}.csv")
def export_report(report_type: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if report_type == "areas":
        rows = [area_payload(item) for item in db.scalars(select(AffectedArea).order_by(AffectedArea.area_id)).all()]
    elif report_type == "requests":
        rows = [request_payload(item) for item in db.scalars(select(EmergencyRequest).order_by(EmergencyRequest.timestamp.desc())).all()]
    elif report_type == "resources":
        rows = [resource_payload(item) for item in db.scalars(select(Resource).order_by(Resource.name)).all()]
    elif report_type == "history":
        rows = [{"id": item.id, "category": item.category, "summary": item.summary, "details": item.details, "created_at": item.created_at} for item in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc())).all()]
    elif report_type == "decisions":
        rows = [{"id": item.id, "run_id": item.run_id, "area_id": item.area_id, "decision": item.decision, "reason": item.reason, "allocation": item.allocation, "created_at": item.created_at} for item in db.scalars(select(Decision).order_by(Decision.created_at.desc())).all()]
    elif report_type == "optimization":
        rows = [{"id": item.id, "status": item.status, "fitness": item.fitness, "generations": item.generations, "created_at": item.created_at} for item in db.scalars(select(OptimizationRun).order_by(OptimizationRun.created_at.desc())).all()]
    else:
        raise HTTPException(status_code=404, detail="Unknown report type")
    columns = list(rows[0].keys()) if rows else ["message"]
    writer.writerow(columns)
    for row in rows:
        writer.writerow([str(row.get(column, "")).replace("\n", " ") for column in columns])
    return Response(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=sahaaya-{report_type}-demo.csv"})


@app.get("/api/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(current_user)):
    metrics = {
        "areas": db.scalar(select(func.count(AffectedArea.id))) or 0,
        "resources": db.scalar(select(func.count(Resource.id))) or 0,
        "pending_requests": db.scalar(select(func.count(EmergencyRequest.id)).where(EmergencyRequest.status == "Pending")) or 0,
        "unread_alerts": db.scalar(select(func.count(Alert.id)).where(Alert.is_read.is_(False))) or 0,
    }
    return {"incident": "MONSOON RESPONSE · DEMO ENVIRONMENT", "demo": True, "notice": "Fictional demonstration data · Not live emergency information", "metrics": metrics}
