import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import fetch_all_product_ids, insert_products, make_timestamps


@pytest.mark.asyncio
async def test_no_duplicates_across_pages(client: AsyncClient, db_session: AsyncSession):
    timestamps = make_timestamps(25)
    await insert_products(
        db_session,
        [
            {
                "name": f"Product {index}",
                "category": "Electronics",
                "price": 10 + index,
                "updated_at": timestamps[index],
            }
            for index in range(25)
        ],
    )

    ids = await fetch_all_product_ids(client, limit=7)
    assert len(ids) == len(set(ids))
    assert len(ids) == 25


@pytest.mark.asyncio
async def test_no_missing_records_across_pages(client: AsyncClient, db_session: AsyncSession):
    timestamps = make_timestamps(30)
    products = await insert_products(
        db_session,
        [
            {
                "name": f"Item {index}",
                "category": "Books",
                "price": 5,
                "updated_at": timestamps[index],
            }
            for index in range(30)
        ],
    )
    expected_ids = {product.id for product in products}

    collected = set(await fetch_all_product_ids(client, limit=8))
    assert collected == expected_ids


@pytest.mark.asyncio
async def test_category_filtering(client: AsyncClient, db_session: AsyncSession):
    timestamps = make_timestamps(6)
    await insert_products(
        db_session,
        [
            {
                "name": "Phone",
                "category": "Electronics",
                "price": 100,
                "updated_at": timestamps[0],
            },
            {
                "name": "Shirt",
                "category": "Clothing",
                "price": 20,
                "updated_at": timestamps[1],
            },
            {
                "name": "Laptop",
                "category": "Electronics",
                "price": 900,
                "updated_at": timestamps[2],
            },
        ],
    )

    response = await client.get("/products", params={"category": "Electronics", "limit": 10})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["products"]) == 2
    assert {item["category"] for item in payload["products"]} == {"Electronics"}


@pytest.mark.asyncio
async def test_invalid_cursor_returns_400(client: AsyncClient):
    response = await client.get("/products", params={"cursor": "not-a-valid-cursor"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid cursor format."


@pytest.mark.asyncio
async def test_category_mismatch_cursor_returns_400(client: AsyncClient, db_session: AsyncSession):
    timestamps = make_timestamps(3)
    await insert_products(
        db_session,
        [
            {
                "name": "A",
                "category": "Electronics",
                "price": 1,
                "updated_at": timestamps[0],
            },
            {
                "name": "B",
                "category": "Clothing",
                "price": 2,
                "updated_at": timestamps[1],
            },
        ],
    )

    first_page = await client.get("/products", params={"limit": 1})
    cursor = first_page.json()["next_cursor"]

    mismatch = await client.get(
        "/products",
        params={"cursor": cursor, "category": "Electronics"},
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"] == "Cursor does not match the requested category filter."


@pytest.mark.asyncio
async def test_snapshot_stable_on_insert(client: AsyncClient, db_session: AsyncSession):
    base = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    timestamps = make_timestamps(20, base=base)
    original = await insert_products(
        db_session,
        [
            {
                "name": f"Stable {index}",
                "category": "Sports",
                "price": 15,
                "updated_at": timestamps[index],
            }
            for index in range(20)
        ],
    )
    original_ids = {product.id for product in original}

    first_page = await client.get("/products", params={"limit": 5})
    assert first_page.status_code == 200
    cursor = first_page.json()["next_cursor"]

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    await insert_products(
        db_session,
        [
            {
                "name": "Inserted During Browse",
                "category": "Sports",
                "price": 99,
                "updated_at": future_time,
            }
        ],
    )

    remaining_ids: list[uuid.UUID] = [
        uuid.UUID(item["id"]) for item in first_page.json()["products"]
    ]
    next_cursor = cursor
    while next_cursor is not None:
        page = await client.get("/products", params={"limit": 5, "cursor": next_cursor})
        assert page.status_code == 200
        body = page.json()
        remaining_ids.extend(uuid.UUID(item["id"]) for item in body["products"])
        next_cursor = body["next_cursor"] if body["has_more"] else None

    assert len(remaining_ids) == len(set(remaining_ids))
    assert set(remaining_ids) == original_ids


@pytest.mark.asyncio
async def test_snapshot_stable_on_update(client: AsyncClient, db_session: AsyncSession):
    base = datetime(2024, 2, 1, 8, 0, tzinfo=timezone.utc)
    timestamps = make_timestamps(15, base=base)
    products = await insert_products(
        db_session,
        [
            {
                "name": f"Catalog {index}",
                "category": "Toys",
                "price": 12,
                "updated_at": timestamps[index],
            }
            for index in range(15)
        ],
    )
    target_id = products[10].id

    first_page = await client.get("/products", params={"limit": 5})
    cursor = first_page.json()["next_cursor"]

    await db_session.execute(
        text("UPDATE products SET name = :name WHERE id = :id"),
        {"name": "Renamed During Browse", "id": target_id},
    )
    await db_session.commit()

    collected = [uuid.UUID(item["id"]) for item in first_page.json()["products"]]
    next_cursor = cursor
    while next_cursor is not None:
        page = await client.get("/products", params={"limit": 5, "cursor": next_cursor})
        body = page.json()
        collected.extend(uuid.UUID(item["id"]) for item in body["products"])
        next_cursor = body["next_cursor"] if body["has_more"] else None

    assert len(collected) == 15
    assert len(collected) == len(set(collected))
    assert target_id in collected


@pytest.mark.asyncio
async def test_products_sorted_newest_first(client: AsyncClient, db_session: AsyncSession):
    timestamps = make_timestamps(5)
    await insert_products(
        db_session,
        [
            {
                "name": f"Sorted {index}",
                "category": "Health",
                "price": 3,
                "updated_at": timestamps[index],
            }
            for index in range(5)
        ],
    )

    response = await client.get("/products", params={"limit": 10})
    products = response.json()["products"]
    observed = [item["updated_at"] for item in products]
    assert observed == sorted(observed, reverse=True)


@pytest.mark.asyncio
async def test_health_check_ok(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
