"""
Seed the database with 200,000 products using batched bulk inserts.

Usage:
    python -m scripts.seed
    python -m scripts.seed --count 200000 --batch-size 5000
"""

from __future__ import annotations

import argparse
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, insert, select, text

from app.database import AsyncSessionLocal, engine
from app.models.product import Product

CATEGORIES = [
    "Electronics",
    "Clothing",
    "Home & Garden",
    "Sports",
    "Books",
    "Toys",
    "Beauty",
    "Automotive",
    "Food",
    "Health",
]

ADJECTIVES = [
    "Premium",
    "Classic",
    "Modern",
    "Eco",
    "Pro",
    "Essential",
    "Deluxe",
    "Compact",
    "Wireless",
    "Smart",
]

NOUNS = [
    "Speaker",
    "Jacket",
    "Lamp",
    "Ball",
    "Novel",
    "Puzzle",
    "Serum",
    "Filter",
    "Snack",
    "Monitor",
    "Bottle",
    "Chair",
    "Router",
    "Blender",
    "Backpack",
]


def _random_name(rng: random.Random) -> str:
    return f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)} {rng.randint(1, 9999)}"


def _generate_batch(
    rng: random.Random,
    batch_size: int,
    base_time: datetime,
) -> list[dict]:
    rows: list[dict] = []
    for offset in range(batch_size):
        # Spread updated_at across a 2-year window so pagination has realistic ordering.
        seconds_ago = rng.randint(0, 63_072_000)
        updated_at = base_time - timedelta(seconds=seconds_ago)
        created_at = updated_at - timedelta(seconds=rng.randint(0, 86_400))

        rows.append(
            {
                "id": uuid.uuid4(),
                "name": _random_name(rng),
                "category": rng.choice(CATEGORIES),
                "price": round(rng.uniform(1.0, 999.99), 2),
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
    return rows


async def seed(count: int, batch_size: int) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(func.count()).select_from(Product))
        if existing and existing >= count:
            print(f"Database already has {existing:,} products. Skipping seed.")
            return

        if existing:
            print(f"Found {existing:,} existing products. Truncating before re-seed.")
            await session.execute(text("TRUNCATE TABLE products"))
            await session.commit()

    rng = random.Random(42)
    base_time = datetime.now(timezone.utc)
    inserted = 0

    print(f"Seeding {count:,} products in batches of {batch_size:,}...")

    while inserted < count:
        current_batch_size = min(batch_size, count - inserted)
        batch = _generate_batch(rng, current_batch_size, base_time)

        async with AsyncSessionLocal() as session:
            await session.execute(insert(Product), batch)
            await session.commit()

        inserted += current_batch_size
        print(f"  Inserted {inserted:,} / {count:,}")

    print("Seed complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed product catalog data.")
    parser.add_argument("--count", type=int, default=200_000, help="Number of products to insert.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5_000,
        help="Rows per bulk insert batch.",
    )
    args = parser.parse_args()

    asyncio.run(seed(count=args.count, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
