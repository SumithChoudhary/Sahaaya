from __future__ import annotations

from typing import Any

from .cwc import CWCConnector
from .gdacs import GDACSConnector
from .imd import IMDConnector
from .nwic import NWICRainfallConnector
from .sachet import SachetConnector
from .usgs import USGSConnector

CONNECTORS: dict[str, Any] = {
    item.source_key: item for item in [IMDConnector(), SachetConnector(), NWICRainfallConnector(),
                                       CWCConnector(), GDACSConnector(), USGSConnector()]
}

SOURCE_CATALOG = [
    {"source_key": "imd_weather", "name": "India Meteorological Department", "provider": "IMD", "category": "weather", "endpoint": "https://api.imd.gov.in/api/v1", "coverage": {"country": "IND", "initial_states": ["Telangana"]}, "requires_credentials": True, "freshness_seconds": 7200, "attribution": "India Meteorological Department", "license_name": "Access governed by IMD account terms", "license_url": "https://api.imd.gov.in/public/"},
    {"source_key": "sachet_cap", "name": "NDMA SACHET CAP alerts", "provider": "NDMA SACHET", "category": "official_warning", "endpoint": None, "coverage": {"country": "IND", "initial_states": ["Telangana"]}, "requires_credentials": True, "freshness_seconds": 1800, "attribution": "National Disaster Management Authority SACHET", "license_name": "Feed subscription terms", "license_url": "https://sachet.ndma.gov.in/CapFeed"},
    {"source_key": "nwic_telangana_rainfall", "name": "NWIC Telangana SW hourly rainfall", "provider": "NWIC / Telangana SW", "category": "rainfall", "endpoint": "https://nwdp.nwic.gov.in/dataset/c41fc083-97c2-4aa2-b03d-4265bd245113/resource/afe7a84b-dc63-4172-8a7f-cadf49403b46/download/rainfall_tel_hr_telangana_sw_ts_2026_2030.csv", "coverage": {"country": "IND", "states": ["Telangana"]}, "requires_credentials": False, "freshness_seconds": 7200, "attribution": "National Water Data Portal / Telangana SW", "license_name": "Other (Open); review resource-specific terms", "license_url": "https://nwdp.nwic.gov.in/dataset/rainfall-telemetry-hourly-telangana-sw", "config": {"resource_ids": ["a6587c58-664a-408e-af7b-d9080dd2f432", "afe7a84b-dc63-4172-8a7f-cadf49403b46"], "column_mapping": {}}},
    {"source_key": "cwc_flood_forecast", "name": "Central Water Commission flood forecasts", "provider": "CWC", "category": "flood_forecast", "endpoint": None, "coverage": {"country": "IND"}, "requires_credentials": True, "freshness_seconds": 3600, "attribution": "Central Water Commission", "license_name": "Verify source-specific terms", "license_url": "https://ffs.india-water.gov.in/"},
    {"source_key": "gdacs_events", "name": "GDACS global disaster events", "provider": "GDACS", "category": "disaster_event", "endpoint": "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH", "coverage": {"global": True}, "requires_credentials": False, "freshness_seconds": 7200, "attribution": "Global Disaster Awareness and Coordination System (GDACS)", "license_name": "GDACS terms; attribution required", "license_url": "https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf"},
    {"source_key": "usgs_earthquakes", "name": "USGS earthquake GeoJSON", "provider": "USGS", "category": "earthquake", "endpoint": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson", "coverage": {"global": True}, "requires_credentials": False, "freshness_seconds": 3600, "attribution": "U.S. Geological Survey", "license_name": "USGS public data; cite source", "license_url": "https://earthquake.usgs.gov/"},
    {"source_key": "historical_import", "name": "Historical dataset imports", "provider": "Operator import", "category": "historical", "endpoint": None, "coverage": {"country": "IND"}, "requires_credentials": False, "freshness_seconds": 0, "attribution": "Dataset attribution supplied at import", "license_name": None, "license_url": None},
]


def ensure_source_catalog(db) -> None:
    from sqlalchemy import select
    from ..models import DataSource

    for item in SOURCE_CATALOG:
        row = db.scalar(select(DataSource).where(DataSource.source_key == item["source_key"]))
        if row is None:
            values = {**item}
            values["config"] = values.pop("config", {})
            values["status"] = "Not configured"
            db.add(DataSource(**values))
        else:
            # Refresh human-readable metadata while preserving operator config and status.
            for key in ("name", "provider", "category", "coverage", "requires_credentials", "freshness_seconds", "attribution", "license_name", "license_url"):
                setattr(row, key, item[key])
            if row.endpoint is None and item["endpoint"]:
                row.endpoint = item["endpoint"]
    db.commit()


def connector_for(source_key: str):
    return CONNECTORS.get(source_key)


def configured_status(source: Any) -> bool:
    connector = connector_for(source.source_key)
    return bool(connector and connector.is_configured(source))
