"""Initial products table and pagination indexes."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_products_updated_at_id_desc",
        "products",
        ["updated_at", "id"],
        unique=False,
        postgresql_ops={"updated_at": "DESC", "id": "DESC"},
    )
    op.create_index(
        "ix_products_category_updated_at_id_desc",
        "products",
        ["category", "updated_at", "id"],
        unique=False,
        postgresql_ops={"updated_at": "DESC", "id": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_products_category_updated_at_id_desc", table_name="products")
    op.drop_index("ix_products_updated_at_id_desc", table_name="products")
    op.drop_table("products")
