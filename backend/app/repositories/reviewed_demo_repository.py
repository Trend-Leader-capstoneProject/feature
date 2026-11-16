"""SELECT-only inspection on the caller's read-only connection."""

from sqlalchemy import String, or_, select, text

from app.models.category import Category
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource


class ReviewedDemoRepository:
    def __init__(self, connection):
        self.connection = connection

    def identity(self):
        row = self.connection.execute(text(
            "SELECT DATABASE() AS database_name, CURRENT_USER() AS authenticated_user"
        )).mappings().one()
        return {"database_name": row["database_name"],
                "current_user": row["authenticated_user"]}

    def categories(self):
        child = Category.__table__.alias("child")
        parent = Category.__table__.alias("parent")
        statement = select(
            child.c.category_id, child.c.category_name,
            parent.c.category_id.label("parent_id"), parent.c.category_code,
        ).select_from(child.join(parent, child.c.parent_id == parent.c.category_id))
        statement = statement.where(
            parent.c.category_code == "IT_DIGITAL", parent.c.parent_id.is_(None),
            parent.c.is_active.is_(True), child.c.is_active.is_(True),
            child.c.category_code.is_(None),
        ).order_by(child.c.sort_order, child.c.category_id)
        return [dict(row) for row in self.connection.execute(statement).mappings()]

    def schema_issues(self):
        rows = self.connection.execute(text(
            "SELECT TABLE_NAME, COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME IN ('trends', 'trend_sources', 'trend_category_map')"
        )).mappings()
        actual = {(row["TABLE_NAME"], row["COLUMN_NAME"]): row for row in rows}
        issues = []
        for model in (Trend, TrendSource, TrendCategoryMap):
            for column in model.__table__.columns:
                key = (model.__tablename__, column.name)
                observed = actual.get(key)
                if observed is None:
                    issues.append({"table": key[0], "column": key[1],
                                   "code": "COLUMN_MISSING"})
                    continue
                if not column.nullable and observed["IS_NULLABLE"] != "NO":
                    issues.append({"table": key[0], "column": key[1],
                                   "code": "REQUIRED_NULLABILITY_MISMATCH"})
                if isinstance(column.type, String) and column.type.length:
                    length = observed["CHARACTER_MAXIMUM_LENGTH"]
                    if length is None or length < column.type.length:
                        issues.append({"table": key[0], "column": key[1],
                                       "code": "STRING_CAPACITY_MISMATCH"})
        return issues

    def duplicates(self, *, title, normalized_title, source_key, source_url,
                   canonical_url):
        trends = Trend.__table__
        sources = TrendSource.__table__
        maps = TrendCategoryMap.__table__
        rows = list(self.connection.execute(select(
            trends.c.trend_id, trends.c.title, trends.c.normalized_title,
        ).where(or_(trends.c.title == title,
                    trends.c.normalized_title == normalized_title))).mappings())
        titles = [row["trend_id"] for row in rows]
        source_hits = list(self.connection.execute(select(sources.c.trend_id).where(
            or_(sources.c.source_key == source_key,
                sources.c.source_url.in_((source_url, canonical_url))),
        )).scalars())
        category_maps = []
        if titles:
            category_maps = [dict(row) for row in self.connection.execute(
                select(maps.c.trend_id, maps.c.category_id).where(
                    maps.c.trend_id.in_(titles),
                )
            ).mappings()]
        return {
            "title_trend_ids": sorted(set(titles)),
            "exact_title_trend_ids": sorted({
                row["trend_id"] for row in rows if row["title"] == title
            }),
            "normalized_title_trend_ids": sorted({
                row["trend_id"] for row in rows
                if row["normalized_title"] == normalized_title
            }),
            "source_trend_ids": sorted(set(source_hits)),
            "existing_category_maps": category_maps,
        }
