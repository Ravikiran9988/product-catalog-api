from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str
    price: Decimal
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    products: list[ProductResponse]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the next page. Pass as the `cursor` query parameter.",
    )
    has_more: bool = Field(
        description="True when additional products exist beyond this page.",
    )
