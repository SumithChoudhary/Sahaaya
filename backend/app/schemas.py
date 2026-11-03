from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class AreaInput(BaseModel):
    area_id: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    population_affected: int = Field(ge=0, le=100_000_000)
    severity: int = Field(ge=1, le=5)
    injured_people: int = Field(ge=0, le=100_000_000)
    trapped_people: int = Field(ge=0, le=100_000_000)
    emergency_requests: int = Field(ge=0, le=100_000_000)
    accessibility: int = Field(ge=1, le=5)
    distance_to_resource_center: float = Field(ge=0, le=50_000)

    @model_validator(mode="after")
    def counts_fit_affected_population(self):
        if self.injured_people > self.population_affected or self.trapped_people > self.population_affected:
            raise ValueError("Injured and trapped counts cannot exceed the affected population")
        return self


class AreaCreate(AreaInput):
    pass


class AreaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    population_affected: int | None = Field(default=None, ge=0)
    severity: int | None = Field(default=None, ge=1, le=5)
    injured_people: int | None = Field(default=None, ge=0)
    trapped_people: int | None = Field(default=None, ge=0)
    emergency_requests: int | None = Field(default=None, ge=0)
    accessibility: int | None = Field(default=None, ge=1, le=5)
    distance_to_resource_center: float | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, max_length=30)


class ResourceInput(BaseModel):
    resource_key: str = Field(min_length=2, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    total: int = Field(ge=0, le=100_000_000)
    available: int = Field(ge=0, le=100_000_000)
    allocated: int = Field(default=0, ge=0)
    deployed: int = Field(default=0, ge=0)
    unit: str = Field(min_length=1, max_length=40)
    center_id: int | None = None

    @field_validator("available")
    @classmethod
    def available_fits_total(cls, value: int, info):
        total = info.data.get("total")
        if total is not None and value > total:
            raise ValueError("Available quantity cannot exceed total")
        return value


class ResourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    total: int | None = Field(default=None, ge=0)
    available: int | None = Field(default=None, ge=0)
    allocated: int | None = Field(default=None, ge=0)
    deployed: int | None = Field(default=None, ge=0)
    unit: str | None = None
    center_id: int | None = None


class CenterInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RequestInput(BaseModel):
    area_id: str
    request_type: Literal["Medical", "Rescue", "Food", "Water", "Shelter", "Evacuation"]
    severity: Literal["Critical", "High", "Medium", "Low"]
    people_affected: int = Field(ge=0, le=100_000_000)
    status: Literal["Pending", "Processing", "Assigned", "Completed"] = "Pending"


class RequestUpdate(BaseModel):
    request_type: Literal["Medical", "Rescue", "Food", "Water", "Shelter", "Evacuation"] | None = None
    severity: Literal["Critical", "High", "Medium", "Low"] | None = None
    people_affected: int | None = Field(default=None, ge=0)
    status: Literal["Pending", "Processing", "Assigned", "Completed"] | None = None


class PriorityInput(AreaInput):
    pass


class GAParameters(BaseModel):
    population_size: int = Field(default=80, ge=10, le=500)
    generations: int = Field(default=100, ge=5, le=1000)
    mutation_rate: float = Field(default=0.08, ge=0, le=1)
    crossover_rate: float = Field(default=0.8, ge=0, le=1)
    seed: int = Field(default=17, ge=0, le=2**31 - 1)


class OptimizationInput(BaseModel):
    parameters: GAParameters = Field(default_factory=GAParameters)
    area_ids: list[str] | None = None


class AllocationChange(BaseModel):
    area_id: str
    allocation: dict[str, int] | None = None
    reason: str | None = Field(default=None, max_length=1000)


class RejectInput(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class DeploymentUpdate(BaseModel):
    deployed: int = Field(ge=0)
    status: Literal["Approved", "Preparing", "Partially deployed", "Deployed", "Paused"]


class ScenarioInput(BaseModel):
    population_change_pct: int = Field(default=0, ge=-90, le=300)
    severity_change_pct: int = Field(default=0, ge=-80, le=200)
    request_change_pct: int = Field(default=0, ge=-90, le=300)
    ambulance_availability_pct: int = Field(default=0, ge=-90, le=100)
    rescue_availability_pct: int = Field(default=0, ge=-90, le=100)
    medical_availability_pct: int = Field(default=0, ge=-90, le=100)


class SettingsInput(BaseModel):
    population_size: int = Field(default=80, ge=10, le=500)
    generations: int = Field(default=100, ge=5, le=1000)
    mutation_rate: float = Field(default=0.08, ge=0, le=1)
    crossover_rate: float = Field(default=0.8, ge=0, le=1)
    critical_threshold: int = Field(default=80, ge=0, le=100)
    high_threshold: int = Field(default=60, ge=0, le=100)


class AlertUpdate(BaseModel):
    is_read: bool


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DecisionOut(ORMModel):
    id: int
    run_id: int
    area_id: str
    decision: str
    reason: str | None
    allocation: dict | None
    created_at: datetime
