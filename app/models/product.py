import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        # Primary pagination index: newest products first (global listing).
        Index(
            "ix_products_updated_at_id_desc",
            updated_at.desc(),
            id.desc(),
        ),
        # Category-filtered pagination: category equality + same sort order.
        Index(
            "ix_products_category_updated_at_id_desc",
            category,
            updated_at.desc(),
            id.desc(),
        ),
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r}>"
