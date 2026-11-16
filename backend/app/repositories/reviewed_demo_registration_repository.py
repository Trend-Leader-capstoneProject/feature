"""Exactly three Core inserts on the service's verified connection."""

from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource


class ReviewedDemoRegistrationRepository:
    def __init__(self, connection):
        self.connection = connection

    def insert_trend(self, *, title, normalized_title, registered_at):
        result = self.connection.execute(Trend.__table__.insert().values(
            title=title, normalized_title=normalized_title, status="ACTIVE",
            summary=None, thumbnail_url=None,
            first_collected_at=registered_at, last_collected_at=registered_at,
        ))
        return result.inserted_primary_key[0]

    def insert_source(self, *, trend_id, source_key, source_url, source_title,
                      registered_at):
        result = self.connection.execute(TrendSource.__table__.insert().values(
            trend_id=trend_id, source_key=source_key, source_url=source_url,
            source_title=source_title, platform="ETC", collected_at=registered_at,
        ))
        return result.inserted_primary_key[0]

    def insert_category_map(self, *, trend_id, registered_at):
        result = self.connection.execute(TrendCategoryMap.__table__.insert().values(
            trend_id=trend_id, category_id=44, is_primary=True,
            created_at=registered_at,
        ))
        return result.inserted_primary_key[0]
