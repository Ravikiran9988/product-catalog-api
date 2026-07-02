# Product Catalog API

> **Production-ready FastAPI backend** for browsing **200,000+ products** using **snapshot-stable cursor pagination**. Built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0 (Async)**, **Alembic**, and **Docker** for high-performance catalog browsing.

---

## 🚀 Live Demo

- **API:** https://product-catalog-api-ag6j.onrender.com
- **Swagger UI:** https://product-catalog-api-ag6j.onrender.com/docs
- **Health Check:** https://product-catalog-api-ag6j.onrender.com/health

---

## ✨ Features

- 🚀 FastAPI with automatic OpenAPI (Swagger) documentation
- 🐘 PostgreSQL with Async SQLAlchemy 2.0
- ⚡ Snapshot-stable Cursor (Keyset) Pagination
- 🔍 Optional Category Filtering
- 🔒 Cursor validation to prevent invalid pagination
- 📦 Alembic database migrations
- 🧪 Integration tests for pagination invariants
- 🌱 Bulk seed script for 200,000+ products
- 🐳 Docker & Docker Compose support
- ⚙️ Environment-based configuration using `.env`

---

## 🛠 Tech Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 (Async)
- asyncpg
- Alembic
- Docker
- Pytest

---

## 📂 Project Structure

```text
.
├── app/
│   ├── api/
│   ├── models/
│   ├── pagination/
│   ├── schemas/
│   ├── services/
│   ├── database.py
│   └── main.py
├── alembic/
├── scripts/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

# ⚡ Quick Start

## Docker (Recommended)

```bash
docker compose up --build

# Seed database
docker compose --profile seed run --rm seed
```

Local URLs

- API → http://localhost:8000
- Swagger → http://localhost:8000/docs
- Health → http://localhost:8000/health

---

## Local Development

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env

alembic upgrade head

uvicorn app.main:app --reload

python -m scripts.seed
```

---

# 🧪 Running Tests

```bash
alembic upgrade head

pytest -v
```

---

# 📖 API

## GET /products

### Query Parameters

| Parameter | Type | Description |
|----------|------|-------------|
| category | string | Optional category filter |
| limit | integer | Default 20 (Maximum 100) |
| cursor | string | Cursor returned by previous page |

### Response

```json
{
  "products": [],
  "next_cursor": "base64_cursor",
  "has_more": true
}
```

---

## GET /health

```json
{
  "status": "ok"
}
```

---

# 🚀 Pagination Design

This project uses **Cursor (Keyset) Pagination** instead of OFFSET pagination.

## Why?

OFFSET pagination becomes slower as page numbers increase because PostgreSQL must skip every previous row.

Cursor pagination performs an efficient index seek.

Benefits

- Constant performance
- No duplicate records
- No skipped records
- Stable browsing
- Ideal for very large datasets

Products are ordered using

```sql
ORDER BY updated_at DESC, id DESC
```

The cursor stores

- Snapshot timestamp
- Category
- Last product updated_at
- Last product id

allowing every request to continue exactly where the previous page ended.

---

# 📈 Database Indexes

```sql
CREATE INDEX ix_products_updated_at_id_desc
ON products(updated_at DESC, id DESC);

CREATE INDEX ix_products_category_updated_at_id_desc
ON products(category, updated_at DESC, id DESC);
```

These indexes allow PostgreSQL to perform **Index Scans** instead of Full Table Scans, keeping pagination fast even with **200,000+ records**.

---

# 🧪 Testing

Tests verify

- Cursor correctness
- Snapshot stability
- Pagination consistency
- No duplicate rows
- No missing rows

Run

```bash
pytest -v
```

---

# ⚙️ Environment Variables

| Variable | Description |
|----------|-------------|
| DATABASE_URL | PostgreSQL connection string |
| DEFAULT_PAGE_LIMIT | Default page size |
| MAX_PAGE_LIMIT | Maximum page size |
| DEBUG | SQL logging |

---

# 🔮 Future Improvements

- JWT Authentication
- Redis Caching
- Signed Cursor Tokens
- Kubernetes Deployment
- Read Replicas
- COPY-based Bulk Loading
- GitHub Actions CI/CD
- Prometheus & Grafana Monitoring

---

# 📄 License

This project is licensed under the **MIT License**.

---

## ⭐ Live Demo

- 🌐 API: https://product-catalog-api-ag6j.onrender.com
- 📚 Swagger UI: https://product-catalog-api-ag6j.onrender.com/docs
- ❤️ Health: https://product-catalog-api-ag6j.onrender.com/health

---

Built with ❤️ using **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, **Docker**, and **Python**.
