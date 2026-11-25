"""Add optional related article links; keep observation sources unchanged.

Revision ID: d3a9f27c6b41
Revises: b7f2c81d9e04
"""

import sqlalchemy as sa
from alembic import op

revision = "d3a9f27c6b41"
down_revision = "b7f2c81d9e04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trend_related_articles",
        sa.Column(
            "article_id", sa.BigInteger(), autoincrement=True,
            nullable=False, comment="관련 기사 ID",
        ),
        sa.Column(
            "trend_id", sa.BigInteger(), nullable=False, comment="부모 트렌드 ID",
        ),
        sa.Column(
            "article_url", sa.Text(), nullable=False,
            comment="승인된 직접 HTTPS 기사 URL",
        ),
        sa.Column(
            "url_key", sa.CHAR(64), nullable=False, comment="정규 기사 URL SHA-256",
        ),
        sa.Column(
            "publisher", sa.String(255), nullable=False, comment="발행 매체",
        ),
        sa.Column(
            "title", sa.String(255), nullable=True,
            comment="이용 근거가 있는 경우만 저장하는 제목",
        ),
        sa.Column(
            "published_at", sa.DateTime(), nullable=False,
            comment="기사 발행 시각(UTC)",
        ),
        sa.Column(
            "collected_at", sa.DateTime(), nullable=False,
            comment="기사 수집 시각(UTC)",
        ),
        sa.Column(
            "selection_order", sa.SmallInteger(), nullable=False,
            comment="기사 표시 순서(1 또는 2)",
        ),
        sa.PrimaryKeyConstraint("article_id", name=op.f("pk_trend_related_articles")),
        sa.ForeignKeyConstraint(
            ["trend_id"], ["trends.trend_id"], ondelete="CASCADE",
            name=op.f("fk_trend_related_articles_trend_id_trends"),
        ),
        sa.UniqueConstraint(
            "trend_id", "url_key",
            name="uq_trend_related_articles_trend_url_key",
        ),
        sa.UniqueConstraint(
            "trend_id", "selection_order",
            name="uq_trend_related_articles_trend_selection_order",
        ),
        sa.CheckConstraint(
            "selection_order IN (1, 2)",
            name="ck_trend_related_articles_selection_order",
        ),
        sa.CheckConstraint(
            "published_at <= collected_at",
            name="ck_trend_related_articles_published_at",
        ),
        comment="트렌드 참고 기사 링크",
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    # Destructive for related articles only; requires separate operational approval.
    op.drop_table("trend_related_articles")
