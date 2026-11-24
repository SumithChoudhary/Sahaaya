from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class ProviderNotConfigured(RuntimeError):
    """The provider needs authorized endpoint or credentials before use."""


@dataclass
class NormalizedRecord:
    kind: str
    external_id: str
    raw: dict[str, Any]
    values: dict[str, Any]
    published_at: datetime | None = None
    source_url: str | None = None


@dataclass
class FetchResult:
    records: list[NormalizedRecord] = field(default_factory=list)
    etag: str | None = None
    not_modified: bool = False
    source_timestamp: datetime | None = None
    message: str | None = None


class Connector(Protocol):
    source_key: str

    def is_configured(self, source: Any) -> bool: ...

    async def fetch(self, source: Any, etag: str | None = None) -> FetchResult: ...
