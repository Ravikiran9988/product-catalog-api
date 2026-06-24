# Product Catalog API

Production-ready FastAPI backend for browsing ~200,000 products with **snapshot-stable cursor pagination**.

## Features

- **FastAPI** with OpenAPI/Swagger at `/docs`
- **PostgreSQL** + **SQLAlchemy 2.0** (async)
- **Snapshot-stable keyset pagination** on `(updated_at DESC, id DESC)`
- Optional **category filtering** bound to the cursor
- **Alembic** migrations (no runtime `create_all`)
- **Integration tests** for pagination invariants
- **Bulk seed script** for 200,000 products
- **Docker** / **docker-compose**
- Configuration via **`.env`**

## Quick Start

### Docker (recommended)

```bash
docker compose up --build

# Seed 200k products (runs migrations first)
docker compose --profile seed run --rm seed
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Local development

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env

# Start PostgreSQL, then:
alembic upgrade head
uvicorn app.main:app --reload
python -m scripts.seed
```

### Run tests

Requires a running PostgreSQL instance (same `DATABASE_URL` as `.env`):

```bash
alembic upgrade head
pytest -v
```

## API

### `GET /products`

| Parameter  | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `category`| string | No       | Exact category filter |
| `limit`   | int    | No       | Page size (default 20, max 100) |
| `cursor`  | string | No       | Opaque cursor from `next_cursor` |

**Response:** `{ products, next_cursor, has_more }`

### `GET /health`

Returns `200` with `{ "status": "ok" }` when the database is reachable, otherwise `503`.

## Architecture

```
Client
  → FastAPI router (validation)
    → ProductService (snapshot + keyset query)
      → SQLAlchemy / asyncpg
        → PostgreSQL (indexed seeks)
  ← PaginationCursor (encode/decode as_of, category, position)
```

| Layer | Responsibility |
|-------|----------------|
| `api/routes` | HTTP params, OpenAPI docs |
| `services` | Snapshot boundary, keyset filter, pagination |
| `pagination/cursor` | Opaque cursor encoding |
| `models` | Schema + indexes |
| `alembic` | Versioned migrations |

## Pagination Design

### Why not OFFSET?

| | OFFSET | Cursor (keyset) |
|---|--------|-----------------|
| Deep pages | Scans and discards rows — O(offset) | Index seek — O(limit) |
| Concurrent writes | Rows shift → duplicates & misses | Position anchored by sort key |
| 200k+ rows | Slow at depth | Constant-time per page |

OFFSET is unsuitable for large, live catalogs.

### Keyset (cursor) pagination

Products sort by **`updated_at DESC, id DESC`**. The `id` tie-breaker guarantees a total order when timestamps collide.

Each page returns `limit + 1` rows; the extra row sets `has_more`. The cursor encodes the last row’s position:

```sql
(updated_at, id) < (:cursor_updated_at, :cursor_id)
ORDER BY updated_at DESC, id DESC
LIMIT :limit
```

Implemented with PostgreSQL **tuple comparison** (not `OR`):

```python
tuple_(Product.updated_at, Product.id) < tuple_(cursor.updated_at, cursor.id)
```

### Snapshot-stable pagination

Concurrent inserts/updates would break a naive live cursor. This API freezes a **snapshot** on the first request:

1. **First page** (no cursor): capture `as_of = now(UTC)`.
2. **All pages** in the session enforce `updated_at <= as_of`.
3. **`as_of` and `category`** are embedded in every cursor.

| Event during browsing | Behavior |
|----------------------|----------|
| New product inserted (`updated_at > as_of`) | Excluded from snapshot |
| Product updated (name/price, `updated_at` unchanged) | Stays in snapshot at same position |
| Product updated (`updated_at > as_of`) | Excluded (sort-key moved past snapshot) |

This gives a consistent, duplicate-free browse of the catalog as it existed at `as_of`.

### Category + cursor binding

The cursor stores the `category` filter from the first request (`null` = no filter). Reusing a cursor with a different `category` returns **400**.

### Cursor payload (opaque to clients)

```json
{
  "a": "2024-06-15T12:00:00+00:00",
  "c": "Electronics",
  "u": "2024-06-14T08:30:00+00:00",
  "i": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

Base64-encoded; clients must pass it back unchanged.

## Index Strategy

```sql
-- Global listing
CREATE INDEX ix_products_updated_at_id_desc
  ON products (updated_at DESC, id DESC);

-- Category-filtered listing
CREATE INDEX ix_products_category_updated_at_id_desc
  ON products (category, updated_at DESC, id DESC);
```

Indexes match `WHERE updated_at <= :as_of [AND category = :cat] AND (keyset) ORDER BY ...`.

### Sample `EXPLAIN ANALYZE` (page 1, 200k rows)

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name, category, price, created_at, updated_at
FROM products
WHERE updated_at <= '2024-06-15T12:00:00+00'
ORDER BY updated_at DESC, id DESC
LIMIT 21;
```

```
Limit  (cost=0.42..2.18 rows=21 width=72) (actual time=0.045..0.112 rows=21 loops=1)
  Buffers: shared hit=24
  ->  Index Scan using ix_products_updated_at_id_desc on products
        (cost=0.42..16642.42 rows=200000 width=72)
        (actual time=0.043..0.108 rows=21 loops=1)
        Index Cond: (updated_at <= '2024-06-15 12:00:00+00')
        Buffers: shared hit=24
Planning Time: 0.15 ms
Execution Time: 0.13 ms
```

**Takeaway:** PostgreSQL uses an **index scan** on the composite index, reads only `limit + 1` rows, and does **not** seq-scan 200k rows. Cost is flat regardless of page depth.

Run after seeding:

```bash
docker compose exec db psql -U postgres -d product_catalog -c \
  "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM products WHERE updated_at <= now() ORDER BY updated_at DESC, id DESC LIMIT 21;"
```

## Tradeoffs & Future Improvements

| Topic | Current choice | Future option |
|-------|---------------|---------------|
| Sort key | `updated_at` | Immutable `listed_at` for stricter update stability |
| Snapshot | `as_of` timestamp | Signed cursors, TTL on browse sessions |
| Categories | Free-text `VARCHAR` | Normalized `categories` table |
| Migrations | Alembic | CI migration gate, zero-downtime deploys |
| Seeding | Batched `INSERT` | `COPY FROM` for millions of rows |
| Ops | Single uvicorn worker | Gunicorn + multiple workers, read replicas |

## Project Structure

```
.
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── api/routes/products.py
│   ├── models/product.py
│   ├── schemas/product.py
│   ├── services/product_service.py
│   └── pagination/cursor.py
├── alembic/
│   └── versions/001_initial_products.py
├── scripts/seed.py
├── tests/
│   ├── conftest.py
│   └── test_pagination.py
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
└── requirements.txt
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/product_catalog` | Async DB URL |
| `DEFAULT_PAGE_LIMIT` | `20` | Default page size |
| `MAX_PAGE_LIMIT` | `100` | Max page size |
| `DEBUG` | `false` | SQL echo logging |

## License

MIT
