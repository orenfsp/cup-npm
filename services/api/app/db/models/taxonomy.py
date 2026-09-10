from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("slug", name="categories_slug"),
        CheckConstraint("slug = lower(btrim(slug))", name="categories_slug_normalized"),
        CheckConstraint("sort_order >= 0", name="categories_nonnegative_sort_order"),
    )

    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class SpecialistGroup(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "specialist_groups"
    __table_args__ = (
        UniqueConstraint("slug", name="specialist_groups_slug"),
        CheckConstraint("slug = lower(btrim(slug))", name="specialist_groups_slug_normalized"),
    )

    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class CategoryGroupRule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "category_group_rules"
    __table_args__ = (
        UniqueConstraint("category_id", "specialist_group_id", name="category_group_rules_pair"),
    )

    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    specialist_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("specialist_groups.id", ondelete="CASCADE"), nullable=False
    )


class CrisisRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Administrator-managed literal phrase; executable patterns are forbidden."""

    __tablename__ = "crisis_rules"
    __table_args__ = (
        UniqueConstraint("normalized_phrase", name="crisis_rules_normalized_phrase"),
        CheckConstraint("phrase = btrim(phrase)", name="crisis_rules_phrase_trimmed"),
        CheckConstraint(
            "normalized_phrase = btrim(normalized_phrase)", name="crisis_rules_normalized_trimmed"
        ),
        CheckConstraint(
            "compact_phrase = btrim(compact_phrase)", name="crisis_rules_compact_trimmed"
        ),
        CheckConstraint(
            "char_length(normalized_phrase) > 0", name="crisis_rules_normalized_nonempty"
        ),
        CheckConstraint("char_length(compact_phrase) > 0", name="crisis_rules_compact_nonempty"),
        CheckConstraint("sort_order >= 0", name="crisis_rules_nonnegative_sort_order"),
    )

    phrase: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_phrase: Mapped[str] = mapped_column(String(300), nullable=False)
    compact_phrase: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    allow_compact_match: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
