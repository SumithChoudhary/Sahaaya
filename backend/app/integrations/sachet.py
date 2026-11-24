from __future__ import annotations

import os
from typing import Any

from xml.etree import ElementTree

from .base import FetchResult, NormalizedRecord, ProviderNotConfigured
from .http import get_response, parse_datetime


def _children(element, tag: str) -> list:
    return [child for child in list(element) if child.tag.rsplit("}", 1)[-1] == tag]


def _text(element, tag: str) -> str | None:
    found = next(iter(_children(element, tag)), None)
    if found is None:
        return None
    return " ".join(found.itertext()).strip() or None


class SachetConnector:
    source_key = "sachet_cap"

    def _url(self, source: Any) -> str:
        return os.getenv("SACHET_CAP_FEED_URL", "").strip() or str(source.endpoint or "").strip()

    def is_configured(self, source: Any) -> bool:
        return bool(self._url(source))

    async def fetch(self, source: Any, etag: str | None = None) -> FetchResult:
        url = self._url(source)
        if not url:
            raise ProviderNotConfigured("Configure the subscribed SACHET CAP feed URL. Do not guess its feed identifier.")
        response = await get_response(url, allowed_hosts={"sachet.ndma.gov.in"}, headers={"If-None-Match": etag} if etag else None)
        if response.status_code == 304:
            return FetchResult(etag=etag, not_modified=True, message="SACHET CAP feed has not changed")
        if b"<!DOCTYPE" in response.content.upper() or b"<!ENTITY" in response.content.upper():
            raise RuntimeError("SACHET XML with document type/entity declarations is rejected")
        try:
            root = ElementTree.fromstring(response.content)
        except Exception as exc:
            raise RuntimeError("SACHET response was not valid safe CAP XML") from exc
        records = []
        alert_nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "alert"]
        if root.tag.rsplit("}", 1)[-1] == "alert":
            alert_nodes = [root]
        for alert in alert_nodes:
            identifier = _text(alert, "identifier")
            if not identifier:
                continue
            infos = _children(alert, "info")
            info = infos[0] if infos else alert
            area = next(iter(_children(info, "area")), None)
            area_desc = _text(area, "areaDesc") if area is not None else None
            headline = _text(info, "headline") or _text(info, "event") or "Official warning"
            description = _text(info, "description")
            instruction = _text(info, "instruction")
            text = " · ".join(part for part in [description, f"Instructions: {instruction}" if instruction else None] if part)
            effective = parse_datetime(_text(info, "effective") or _text(info, "onset"))
            expires = parse_datetime(_text(info, "expires"))
            records.append(NormalizedRecord(
                kind="incident", external_id=identifier,
                raw={"identifier": identifier, "sender": _text(alert, "sender"), "sent": _text(alert, "sent"),
                     "status": _text(alert, "status"), "msgType": _text(alert, "msgType"), "source": _text(alert, "source"),
                     "event": _text(info, "event"), "severity": _text(info, "severity"), "urgency": _text(info, "urgency"),
                     "certainty": _text(info, "certainty"), "headline": headline, "description": description,
                     "instruction": instruction, "areaDesc": area_desc, "effective": effective.isoformat() if effective else None,
                     "expires": expires.isoformat() if expires else None},
                values={"hazard_type": str(_text(info, "event") or "warning").lower(), "title": headline,
                        "description": text, "severity": _text(info, "severity"), "urgency": _text(info, "urgency"),
                        "certainty": _text(info, "certainty"), "status": str(_text(alert, "status") or "Actual").lower(),
                        "is_official_warning": True, "latitude": None, "longitude": None, "geometry": None,
                        "area_description": area_desc, "source_published_at": parse_datetime(_text(alert, "sent")),
                        "effective_at": effective, "expires_at": expires, "source_url": url},
                published_at=parse_datetime(_text(alert, "sent")), source_url=url,
            ))
        return FetchResult(records=records, etag=response.headers.get("ETag"), message="SACHET CAP feed fetched with ETag support")
