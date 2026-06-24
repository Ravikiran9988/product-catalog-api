from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.pagination.cursor import PaginationCursor
from app.schemas.product import ProductListResponse, ProductResponse


def _snapshot_as_of() -> datetime:
    return datetime.now(timezone.utc)


def _keyset_filter(cursor: PaginationCursor):
    """
    Rows strictly older than the cursor in (updated_at DESC, id DESC) order.

    PostgreSQL tuple comparison equivalent to:
        (updated_at, id) < (:updated_at, :id)
    """
    return tuple_(Product.updated_at, Product.id) < tuple_(cursor.updated_at, cursor.id)


class ProductService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_products(
        self,
        *,
        category: str | None,
        limit: int,
        cursor: str | None,
    ) -> ProductListResponse:
        if cursor is None:
            as_of = _snapshot_as_of()
            decoded: PaginationCursor | None = None
        else:
            decoded = PaginationCursor.decode(cursor)
            if decoded.category != category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cursor does not match the requested category filter.",
                )
            as_of = decoded.as_of

        stmt = select(Product).where(Product.updated_at <= as_of)

        if category is not None:
            stmt = stmt.where(Product.category == category)

        if decoded is not None:
            stmt = stmt.where(_keyset_filter(decoded))

        stmt = stmt.order_by(Product.updated_at.desc(), Product.id.desc()).limit(limit + 1)

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        page_rows = rows[:limit]

        next_cursor: str | None = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = PaginationCursor.from_product(
                as_of=as_of,
                category=category,
                updated_at=last.updated_at,
                product_id=last.id,
            ).encode()

        return ProductListResponse(
            products=[ProductResponse.model_validate(row) for row in page_rows],
            next_cursor=next_cursor,
            has_more=has_more,
        )
