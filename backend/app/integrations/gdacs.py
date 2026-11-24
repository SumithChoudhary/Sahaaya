from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import FetchResult, NormalizedRecord
from .http import get_response, parse_datetime, validate_coordinates

DEFAULT_URL = "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH"


class GDACSConnector:
    source_key = "gdacs_events"

    def is_configured(self, source: Any) -> bool:
        return bool(os.getenv("GDACS_EVENTS_URL", source.endpoint or DEFAULT_URL))

    async def fetch(self, source: Any, etag: str | None = None) -> FetchResult:
        url = os.getenv("GDACS_EVENTS_URL", source.endpoint or DEFAULT_URL)
        params = {"eventlist": "EQ;FL;TC", "fromdate": (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat(),
                  "todate": datetime.now(timezone.utc).date().isoformat(), "alertlevel": "red;orange;green"}
        response = await get_response(url, allowed_hosts={"www.gdacs.org", "gdacs.org"}, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("GDACS returned invalid JSON") from exc
        features = payload.get("features", []) if isinstance(payload, dict) else []
        if not isinstance(features, list):
            raise RuntimeError("GDACS response did not contain a feature list")
        records = []
        for feature in features:
            props = feature.get("properties") or {}
            external_id = str(props.get("eventid") or props.get("eventId") or feature.get("id") or "").strip()
            event_type = str(props.get("eventtype") or props.get("eventType") or "unknown").lower()
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates") or []
            location = validate_coordinates(coords[1], coords[0]) if geometry.get("type") == "Point" and len(coords) >= 2 else None
            if not external_id:
                continue
            records.append(NormalizedRecord(
                kind="incident", external_id=f"{event_type}:{external_id}", raw=feature,
                values={
                    "hazard_type": {"eq": "earthquake", "fl": "flood", "tc": "tropical_cyclone"}.get(event_type, event_type),
                    "title": str(props.get("name") or props.get("title") or f"GDACS {event_type} event {external_id}"),
                    "description": props.get("description"), "severity": str(props.get("alertlevel") or "Unknown"),
                    "magnitude": props.get("magnitude") or props.get("mag"), "depth_km": props.get("depth"),
                    "status": "observed", "is_official_warning": False,
                    "latitude": location[0] if location else None, "longitude": location[1] if location else None,
                    "geometry": geometry if geometry else None, "area_description": props.get("country") or props.get("countryname"),
                    "source_published_at": parse_datetime(props.get("fromdate") or props.get("todate") or props.get("toDate")),
                    "source_updated_at": parse_datetime(props.get("todate") or props.get("toDate")),
                    "effective_at": parse_datetime(props.get("fromdate")), "expires_at": parse_datetime(props.get("todate")),
                    "source_url": props.get("url") or props.get("url_report"),
                }, published_at=parse_datetime(props.get("fromdate")) or parse_datetime(props.get("todate") or props.get("toDate")),
                source_url=props.get("url") or props.get("url_report"),
            ))
        return FetchResult(records=records, etag=response.headers.get("ETag"), message="GDACS search feed fetched")
