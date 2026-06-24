"""Shared fixtures for integration tests (requires PostgreSQL)."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import get_db
from app.models.base import Base
from app.main import app
from app.models.product import Product

settings = get_settings()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as http_client:
        yield http_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def clean_products(db_engine):
    yield
    async with db_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE products"))


async def insert_products(
    session: AsyncSession,
    specs: list[dict],
) -> list[Product]:
    products: list[Product] = []
    for spec in specs:
        product = Product(
            id=spec.get("id", uuid.uuid4()),
            name=spec["name"],
            category=spec["category"],
            price=Decimal(str(spec["price"])),
            created_at=spec.get("created_at", datetime.now(timezone.utc)),
            updated_at=spec["updated_at"],
        )
        products.append(product)
    session.add_all(products)
    await session.commit()
    return products


def make_timestamps(count: int, *, base: datetime | None = None) -> list[datetime]:
    anchor = base or datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    return [anchor - timedelta(hours=index) for index in range(count)]


async def fetch_all_product_ids(
    client: AsyncClient,
    *,
    limit: int = 10,
    category: str | None = None,
) -> list[uuid.UUID]:
    collected: list[uuid.UUID] = []
    cursor: str | None = None

    while True:
        params: dict[str, str | int] = {"limit": limit}
        if category is not None:
            params["category"] = category
        if cursor is not None:
            params["cursor"] = cursor

        response = await client.get("/products", params=params)
        assert response.status_code == 200, response.text
        payload = response.json()

        for item in payload["products"]:
            collected.append(uuid.UUID(item["id"]))

        if not payload["has_more"]:
            break

        cursor = payload["next_cursor"]
        assert cursor is not None

    return collected
