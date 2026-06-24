"""
Cursor (keyset) pagination utilities with snapshot stability.

Each cursor encodes:
- as_of: snapshot boundary captured on the first page request
- category: filter bound at snapshot time (null = no filter)
- updated_at, id: keyset position of the last item on the current page

Sort order: (updated_at DESC, id DESC) with id as tie-breaker.
"""

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class PaginationCursor:
    as_of: datetime
    category: str | None
    updated_at: datetime
    id: UUID

    def encode(self) -> str:
        payload = {
            "a": _ensure_utc(self.as_of).isoformat(),
            "c": self.category,
            "u": _ensure_utc(self.updated_at).isoformat(),
            "i": str(self.id),
        }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    @classmethod
    def decode(cls, cursor: str) -> "PaginationCursor":
        try:
            raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
            payload = json.loads(raw.decode("utf-8"))
            return cls(
                as_of=_ensure_utc(datetime.fromisoformat(payload["a"])),
                category=payload.get("c"),
                updated_at=_ensure_utc(datetime.fromisoformat(payload["u"])),
                id=UUID(payload["i"]),
            )
        except (KeyError, ValueError, json.JSONDecodeError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor format.",
            ) from exc

    @classmethod
    def from_product(
        cls,
        *,
        as_of: datetime,
        category: str | None,
        updated_at: datetime,
        product_id: UUID,
    ) -> "PaginationCursor":
        return cls(
            as_of=as_of,
            category=category,
            updated_at=updated_at,
            id=product_id,
        )
