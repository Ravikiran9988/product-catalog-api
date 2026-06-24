from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.schemas.product import ProductListResponse
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])
settings = get_settings()


@router.get(
    "",
    response_model=ProductListResponse,
    summary="List products",
    description=(
        "Returns products ordered by `updated_at` descending (newest first). "
        "Uses snapshot-stable cursor pagination: the first request captures an "
        "`as_of` timestamp that is enforced on all subsequent pages. "
        "Category filters are bound to the cursor."
    ),
)
async def list_products(
    category: str | None = Query(
        default=None,
        description="Filter products by exact category name.",
        examples=["Electronics"],
    ),
    limit: int = Query(
        default=settings.default_page_limit,
        ge=1,
        le=settings.max_page_limit,
        description="Maximum number of products to return per page.",
    ),
    cursor: str | None = Query(
        default=None,
        description=(
            "Opaque pagination cursor from a previous response's `next_cursor`. "
            "Omit for the first page."
        ),
    ),
    db: AsyncSession = Depends(get_db),
) -> ProductListResponse:
    service = ProductService(db)
    return await service.list_products(category=category, limit=limit, cursor=cursor)
