"""relax category name uniqueness

Revision ID: a4d7c9e21f3b
Revises: 7e9d740c5df1
Create Date: 2026-09-08 13:24:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a4d7c9e21f3b"
down_revision: Union[str, Sequence[str], None] = "7e9d740c5df1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow the same category display name under different parents."""

    op.drop_constraint(
        "uq_categories_category_name",
        "categories",
        type_="unique",
    )
    op.create_index(
        "ix_categories_parent_id_category_name",
        "categories",
        ["parent_id", "category_name"],
        unique=False,
    )


def downgrade() -> None:
    """Restore the previous global category-name uniqueness."""

    op.drop_index(
        "ix_categories_parent_id_category_name",
        table_name="categories",
    )
    op.create_unique_constraint(
        "uq_categories_category_name",
        "categories",
        ["category_name"],
    )
