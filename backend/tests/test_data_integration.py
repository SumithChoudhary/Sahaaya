from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.api_v1 import HistoricalImportMapping, _preview, _source_health
from backend.app.db import Base
from backend.app.integrations.base import NormalizedRecord
from backend.app.integrations.registry import SOURCE_CATALOG
from backend.app.integrations.usgs import USGSConnector
from backend.app.models import AffectedArea, DataSource, Deployment, GeographicLocation, Incident, Resource, ResourceCenter, ResourceInventory, User, WeatherObservation
from backend.app.schemas import AllocationChange, GAParameters, OptimizationInput
from backend.app.main import approve, run_optimization
from backend.app.services.ingestion import _store_raw
from backend.app.services.ingestion import _upsert_weather
from backend.app.services.optimizer import optimize


class DataIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name) / 'test.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_coordinate_constraints_and_location_hierarchy_persist(self):
        with self.Session() as db:
            state = GeographicLocation(source="test", external_code="state:TS", name="Telangana", level="state", state_code="TS")
            db.add(state)
            db.flush()
            district = GeographicLocation(source="test", external_code="district:HYD", name="Hyderabad", level="district", parent_id=state.id, state_code="TS", district_code="HYD")
            db.add(district)
            db.commit()
            self.assertEqual(db.get(GeographicLocation, district.id).parent.name, "Telangana")
            db.add(Incident(source_id=999, external_record_id="bad", hazard_type="test", title="bad", latitude=91, longitude=78))
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_raw_payload_deduplication_and_revisions(self):
        with self.Session() as db:
            source = DataSource(source_key="test", name="Test", provider="test", category="test")
            db.add(source)
            db.flush()
            record = NormalizedRecord(kind="raw", external_id="x1", raw={"value": 1}, values={}, published_at=None, source_url=None)
            first, duplicate = _store_raw(db, source, record)
            self.assertFalse(duplicate)
            same, duplicate = _store_raw(db, source, record)
            self.assertTrue(duplicate)
            changed, duplicate = _store_raw(db, source, NormalizedRecord(kind="raw", external_id="x1", raw={"value": 2}, values={}, published_at=None, source_url=None))
            self.assertFalse(duplicate)
            self.assertEqual((first.revision, same.revision, changed.revision), (1, 1, 2))

    def test_weather_normalization_attaches_geographic_codes(self):
        with self.Session() as db:
            source = DataSource(source_key="nwic_telangana_rainfall", name="NWIC", provider="NWIC", category="rainfall")
            db.add(source)
            db.flush()
            observed = datetime.now(timezone.utc) - timedelta(hours=1)
            item = NormalizedRecord(kind="weather", external_id="station-1:rainfall", raw={"rain": 1}, published_at=observed, source_url=None,
                values={"variable":"rainfall", "value":1.0, "unit":"mm", "observed_at":observed,
                    "latitude":17.38, "longitude":78.48, "location_name":"Station 1", "state_name":"Telangana",
                    "state_code":"TS", "district_name":"Hyderabad", "district_code":"HYD"})
            raw, _ = _store_raw(db, source, item)
            _upsert_weather(db, source, raw, item)
            observation = db.scalar(select(WeatherObservation))
            self.assertEqual(observation.location.state_code, "TS")
            self.assertEqual(observation.location.district_code, "HYD")
            self.assertEqual(observation.location.parent.name, "Hyderabad")

    def test_historical_preview_rejects_future_and_invalid_coordinates(self):
        mapping = HistoricalImportMapping(timestamp_column="at", value_column="mm", variable="rainfall", unit="mm", latitude_column="lat", longitude_column="lon")
        now = datetime.now(timezone.utc)
        rows = [
            {"at": (now - timedelta(hours=1)).isoformat(), "mm": "2.5", "lat": "17.4", "lon": "78.4"},
            {"at": (now + timedelta(days=1)).isoformat(), "mm": "4", "lat": "17.4", "lon": "78.4"},
            {"at": (now - timedelta(hours=2)).isoformat(), "mm": "4", "lat": "91", "lon": "78.4"},
        ]
        valid, errors = _preview(rows, mapping)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(errors), 2)
        with self.assertRaises(ValueError):
            HistoricalImportMapping(timestamp_column="at", value_column="mm", variable="rainfall", unit="mm", latitude_column="lat")

    def test_usgs_connector_normalizes_verified_geojson_shape(self):
        payload = {"type": "FeatureCollection", "features": [{"id": "us7000test", "properties": {"title": "M 4.2 - test", "mag": 4.2, "time": 1790000000000, "updated": 1790000000100, "place": "Demo only", "url": "https://earthquake.usgs.gov/test"}, "geometry": {"type": "Point", "coordinates": [78.47, 17.38, 10]}}]}
        result = USGSConnector.parse_payload(payload, "https://earthquake.usgs.gov/feed")
        self.assertEqual(result[0].external_id, "us7000test")
        self.assertEqual(result[0].values["latitude"], 17.38)
        self.assertEqual(result[0].values["longitude"], 78.47)
        self.assertEqual(result[0].values["magnitude"], 4.2)
        self.assertEqual(result[0].values["depth_km"], 10)

    def test_source_freshness_classification(self):
        source = SimpleNamespace(source_key="historical_import", last_success_at=None)
        self.assertEqual(_source_health(source), "Not configured")
        source = SimpleNamespace(source_key="test", is_enabled=True, last_success_at=datetime.now(timezone.utc), freshness_seconds=60)
        with patch("backend.app.api_v1.configured_status", return_value=True):
            self.assertEqual(_source_health(source), "Fresh")
        source.last_success_at = datetime.now(timezone.utc) - timedelta(hours=2)
        with patch("backend.app.api_v1.configured_status", return_value=True):
            self.assertEqual(_source_health(source), "Stale")

    def test_optimizer_enforces_area_demand_and_global_supply(self):
        areas = [{"area_id": "A", "name": "A", "latitude": 17.4, "longitude": 78.4, "priority_class": "Critical", "priority_score": 90},
                 {"area_id": "B", "name": "B", "latitude": 17.5, "longitude": 78.5, "priority_class": "High", "priority_score": 70}]
        demands = [{"area_id": "A", "estimated_demand": {"ambulances": 5}}, {"area_id": "B", "estimated_demand": {"ambulances": 6}}]
        result = optimize(areas, demands, [{"resource_key": "ambulances", "available": 7}], [], {"population_size": 10, "generations": 5, "mutation_rate": .1, "crossover_rate": .8, "seed": 5})
        self.assertLessEqual(sum(row["allocated"]["ambulances"] for row in result["results"]), 7)
        for row in result["results"]:
            self.assertLessEqual(row["allocated"]["ambulances"], row["required"]["ambulances"])
        self.assertTrue(result["human_review_required"])
        self.assertFalse(result["dispatch_automatic"])

    def test_optimizer_obeys_each_center_stock(self):
        areas = [{"area_id":"A", "name":"A", "latitude":17.4, "longitude":78.4, "priority_class":"Critical", "priority_score":90},
                 {"area_id":"B", "name":"B", "latitude":17.6, "longitude":78.6, "priority_class":"High", "priority_score":70}]
        demands = [{"area_id":"A", "estimated_demand":{"ambulances":5}}, {"area_id":"B", "estimated_demand":{"ambulances":5}}]
        resources = [{"id":1,"resource_key":"ambulances","available":3,"center_id":1,"center_name":"North"},
                     {"id":2,"resource_key":"ambulances","available":2,"center_id":2,"center_name":"South"}]
        centers = [{"id":1,"name":"North","latitude":17.4,"longitude":78.4}, {"id":2,"name":"South","latitude":17.6,"longitude":78.6}]
        result = optimize(areas, demands, resources, centers, {"population_size":10,"generations":5,"mutation_rate":.1,"crossover_rate":.8,"seed":9})
        self.assertEqual(sum(row["allocated"]["ambulances"] for row in result["results"]), 5)
        self.assertEqual(sum(row["allocated_by_center"]["ambulances"].get("1",0) for row in result["results"]), 3)
        self.assertEqual(sum(row["allocated_by_center"]["ambulances"].get("2",0) for row in result["results"]), 2)

    def test_human_approval_creates_deployment_record(self):
        with self.Session() as db:
            user = User(name="Test Officer", email="officer@test.local", password_hash="not-used", role="Emergency Officer")
            center = ResourceCenter(name="Test center", latitude=17.4, longitude=78.4, is_demo=False)
            db.add_all([user, center])
            db.flush()
            area = AffectedArea(area_id="TEST-1", name="Test area", latitude=17.4, longitude=78.4,
                population_affected=100, severity=5, injured_people=10, trapped_people=5,
                emergency_requests=5, accessibility=2, distance_to_resource_center=1,
                priority_score=90, priority_class="Critical", status="Review", disaster_id=None)
            db.add(area)
            db.add(Resource(resource_key="ambulances", name="Ambulances", total=10, available=10, allocated=0,
                            deployed=0, unit="vehicles", center_id=center.id))
            stock = ResourceInventory(center_id=center.id, resource_key="ambulances", name="Ambulances", total=10,
                available=10, allocated=0, deployed=0, unit="vehicles", quality_status="manually_verified")
            db.add(stock)
            db.commit()
            run = run_optimization(OptimizationInput(parameters=GAParameters(population_size=10, generations=5), area_ids=["TEST-1"]), db, user)
            self.assertEqual(run["status"], "pending_review")
            decision = approve(run["id"], AllocationChange(area_id="TEST-1"), db, user)
            self.assertFalse(decision["automatic_dispatch"])
            self.assertGreater(db.query(Deployment).filter_by(run_id=run["id"], area_id="TEST-1").count(), 0)
            self.assertLess(stock.available, 10)
            self.assertEqual(db.query(Deployment).filter_by(run_id=run["id"], area_id="TEST-1").first().center_id, center.id)

    def test_migration_upgrade_preserves_existing_rows(self):
        db_path = Path(self.temp.name) / "migration.db"
        project_root = Path(__file__).resolve().parents[2]
        config = Config(str(project_root / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(project_root / "backend" / "migrations"))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
        with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}):
            command.upgrade(config, "0001_initial_schema")
            legacy_engine = create_engine(f"sqlite:///{db_path}")
            try:
                with legacy_engine.begin() as connection:
                    connection.execute(User.__table__.insert().values(name="Legacy user", email="legacy@test.local",
                        password_hash="hash", role="Viewer", is_active=True,
                        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            finally:
                legacy_engine.dispose()
            command.upgrade(config, "head")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as connection:
                self.assertIn("historical_observations", set(__import__("sqlalchemy").inspect(connection).get_table_names()))
                columns = {item["name"] for item in __import__("sqlalchemy").inspect(connection).get_columns("historical_observations")}
                self.assertTrue({"latitude", "longitude", "location_name"}.issubset(columns))
                self.assertEqual(connection.execute(User.__table__.select().where(User.email == "legacy@test.local")).first().name, "Legacy user")
                self.assertIn("resource_inventory", set(__import__("sqlalchemy").inspect(connection).get_table_names()))
                self.assertIn("center_id", {item["name"] for item in __import__("sqlalchemy").inspect(connection).get_columns("resource_allocations")})
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
