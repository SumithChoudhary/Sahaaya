from __future__ import annotations

import os
from typing import Any

from .base import FetchResult, NormalizedRecord
from .http import get_response, parse_datetime, validate_coordinates

DEFAULT_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"


class USGSConnector:
    source_key = "usgs_earthquakes"

    def is_configured(self, source: Any) -> bool:
        return bool(os.getenv("USGS_EARTHQUAKE_URL", source.endpoint or DEFAULT_URL))

    @staticmethod
    def parse_payload(payload: dict, source_url: str) -> list[NormalizedRecord]:
        if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
            raise RuntimeError("USGS response was not a GeoJSON FeatureCollection")
        records = []
        for feature in payload["features"]:
            props = feature.get("properties") or {}
            external_id = str(feature.get("id") or props.get("code") or "").strip()
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []
            location = validate_coordinates(coordinates[1], coordinates[0]) if len(coordinates) >= 2 else None
            if not external_id or location is None:
                continue
            latitude, longitude = location
            records.append(NormalizedRecord(
                kind="incident", external_id=external_id, raw=feature,
                values={
                    "hazard_type": "earthquake", "title": str(props.get("title") or "Earthquake event"),
                    "description": props.get("place"), "severity": str(props.get("alert") or "Unknown"),
                    "magnitude": props.get("mag"), "depth_km": coordinates[2] if len(coordinates) > 2 else None,
                    "status": "observed", "is_official_warning": False,
                    "latitude": latitude, "longitude": longitude,
                    "geometry": geometry, "area_description": props.get("place"),
                    "source_published_at": parse_datetime(props.get("time")),
                    "source_updated_at": parse_datetime(props.get("updated")),
                    "effective_at": parse_datetime(props.get("time")),
                    "expires_at": None, "source_url": props.get("url"),
                }, published_at=parse_datetime(props.get("updated")) or parse_datetime(props.get("time")),
                source_url=props.get("url") or source_url,
            ))
        return records

    async def fetch(self, source: Any, etag: str | None = None) -> FetchResult:
        url = os.getenv("USGS_EARTHQUAKE_URL", source.endpoint or DEFAULT_URL)
        headers = {"If-None-Match": etag} if etag else None
        response = await get_response(url, allowed_hosts={"earthquake.usgs.gov"}, headers=headers)
        if response.status_code == 304:
            return FetchResult(etag=etag, not_modified=True, message="USGS feed has not changed")
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("USGS returned invalid JSON") from exc
        records = self.parse_payload(payload, url)
        return FetchResult(records=records, etag=response.headers.get("ETag"), message="USGS GeoJSON feed fetched")
