import json
from datetime import datetime

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.db_enums import CategoryCode, TrendStatus
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.repositories.trend_repository import TrendRepository

pytestmark = pytest.mark.integration

def print_runtime_metrics(node: object) -> None:
    """ANALYZE JSON에서 주요 실제 실행 통계를 출력한다."""

    if isinstance(node, list):
        for item in node:
            print_runtime_metrics(item)
        return

    if not isinstance(node, dict):
        return

    if "table_name" in node:
        fields = (
            "table_name",
            "access_type",
            "key",
            "rows",
            "r_rows",
            "r_loops",
            "r_total_time_ms",
            "r_table_time_ms",
        )

        print(
            "TABLE:",
            {
                field: node[field]
                for field in fields
                if field in node
            },
        )

    if isinstance(node.get("filesort"), dict):
        filesort = node["filesort"]

        print(
            "FILESORT:",
            {
                key: value
                for key, value in filesort.items()
                if key.startswith("r_")
            },
        )

    for value in node.values():
        if isinstance(value, (dict, list)):
            print_runtime_metrics(value)


def test_personalized_trend_page_explain_small_scope(
    db_session: Session,
) -> None:
    """실제 Trend Page SELECT의 MariaDB 실행 계획을 관찰한다."""

    # 1. 테스트용 Root와 활성 Child 생성
    root = Category(
        category_code=None,
        category_name="EXPLAIN Small Root",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )
    db_session.add(root)
    db_session.flush()

    child = Category(
        category_code=None,
        category_name="EXPLAIN Small Child",
        sort_order=1,
        is_active=True,
        parent_id=root.category_id,
    )
    db_session.add(child)
    db_session.flush()

    # 2. ACTIVE Trend와 Category 매핑
    collected_at = datetime(2026, 10, 9, 12, 0, 0)

    trend = Trend(
        title="EXPLAIN Small Trend",
        normalized_title="explain-small-trend",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )
    db_session.add(trend)
    db_session.flush()

    db_session.add(
        TrendCategoryMap(
            trend_id=trend.trend_id,
            category_id=child.category_id,
            is_primary=False,
        )
    )
    db_session.flush()

    # 3. 실제 Repository SELECT SQL과 파라미터 수집
    captured_sql = []

    def capture_sql(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        normalized = " ".join(statement.lower().split())

        if (
            normalized.startswith("select")
            and "from trends" in normalized
            and "trend_category_map" in normalized
        ):
            captured_sql.append((statement, parameters))

    connection = db_session.connection()

    event.listen(
        connection,
        "before_cursor_execute",
        capture_sql,
    )

    try:
        rows = TrendRepository(db_session).find_page(
            limit=21,
            category_ids=[child.category_id],
            cursor_last_collected_at=None,
            cursor_trend_id=None,
        )
    finally:
        event.remove(
            connection,
            "before_cursor_execute",
            capture_sql,
        )

    assert [row.trend_id for row in rows] == [trend.trend_id]
    assert len(captured_sql) == 1

    # 4. 수집한 실제 SELECT를 EXPLAIN
    statement, parameters = captured_sql[0]

    explain_result = connection.exec_driver_sql(
        "EXPLAIN " + statement,
        parameters,
    )

    plans = [
        dict(row)
        for row in explain_result.mappings()
    ]

    assert plans

    print("\n=== MariaDB EXPLAIN: Small Scope ===")

    for plan in plans:
        print(
            {
                "table": plan.get("table"),
                "type": plan.get("type"),
                "possible_keys": plan.get("possible_keys"),
                "key": plan.get("key"),
                "rows": plan.get("rows"),
                "Extra": plan.get("Extra"),
            }
        )


def test_personalized_trend_page_explain_wide_scope(
    db_session: Session,
) -> None:
    """동일한 데이터에서 좁은/넓은 Child Scope의 실행 계획을 비교한다."""

    # 1. Root 6개와 활성 Child 24개 생성
    roots = [
        Category(
            category_code=code,
            category_name=f"EXPLAIN Wide Root {code.value}",
            sort_order=index,
            is_active=True,
            parent_id=None,
        )
        for index, code in enumerate(CategoryCode)
    ]

    db_session.add_all(roots)
    db_session.flush()

    children = [
        Category(
            category_code=None,
            category_name=(
                f"EXPLAIN Wide Child {root_index}-{child_index}"
            ),
            sort_order=child_index,
            is_active=True,
            parent_id=root.category_id,
        )
        for root_index, root in enumerate(roots)
        for child_index in range(4)
    ]

    db_session.add_all(children)
    db_session.flush()

    assert len(children) == 24

    # 2. ACTIVE Trend 25개 생성
    collected_at = datetime(2026, 10, 9, 12, 0, 0)

    trends = [
        Trend(
            title=f"EXPLAIN Wide Trend {index}",
            normalized_title=f"explain-wide-trend-{index}",
            summary=None,
            thumbnail_url=None,
            status=TrendStatus.ACTIVE,
            first_collected_at=collected_at,
            last_collected_at=collected_at,
            updated_at=None,
        )
        for index in range(25)
    ]

    db_session.add_all(trends)
    db_session.flush()

    # 3. 각 Trend를 서로 다른 Child 두 개에 매핑
    mappings = []

    for index, trend in enumerate(trends):
        for child_index in (
            index % len(children),
            (index + 1) % len(children),
        ):
            mappings.append(
                TrendCategoryMap(
                    trend_id=trend.trend_id,
                    category_id=children[child_index].category_id,
                    is_primary=False,
                )
            )

    db_session.add_all(mappings)
    db_session.flush()

    # 4. 실제 Repository SELECT 기록
    captured_sql = []

    def capture_sql(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        normalized = " ".join(statement.lower().split())

        if (
            normalized.startswith("select")
            and "from trends" in normalized
            and "trend_category_map" in normalized
        ):
            captured_sql.append((statement, parameters))

    connection = db_session.connection()
    repository = TrendRepository(db_session)

    small_scope = [children[0].category_id]
    wide_scope = [child.category_id for child in children]

    event.listen(
        connection,
        "before_cursor_execute",
        capture_sql,
    )

    try:
        small_rows = repository.find_page(
            limit=21,
            category_ids=small_scope,
            cursor_last_collected_at=None,
            cursor_trend_id=None,
        )

        wide_rows = repository.find_page(
            limit=21,
            category_ids=wide_scope,
            cursor_last_collected_at=None,
            cursor_trend_id=None,
        )
    finally:
        event.remove(
            connection,
            "before_cursor_execute",
            capture_sql,
        )

    # 5. 두 Scope에서 실제 조회 결과 확인
    assert len(small_rows) == 3
    assert len(wide_rows) == 21
    assert len(captured_sql) == 2

    # 6. 동일한 데이터에서 EXPLAIN 비교
    for label, (statement, parameters) in zip(
        ("Small Scope (1 Child)", "Wide Scope (24 Children)"),
        captured_sql,
        strict=True,
    ):
        result = connection.exec_driver_sql(
            "EXPLAIN " + statement,
            parameters,
        )

        plans = list(result.mappings())

        assert plans

        print(f"\n=== MariaDB EXPLAIN: {label} ===")

        for plan in plans:
            print({
                "table": plan.get("table"),
                "type": plan.get("type"),
                "key": plan.get("key"),
                "rows": plan.get("rows"),
                "Extra": plan.get("Extra"),
            })

        # 7. 실제 SELECT를 실행하여 Runtime 통계 확보
        analyze_result = connection.exec_driver_sql(
            "ANALYZE FORMAT=JSON " + statement,
            parameters,
        ).scalar_one()

        analyze_data = json.loads(analyze_result)

        assert "query_block" in analyze_data

        query_block = analyze_data["query_block"]

        print(f"\n=== MariaDB ANALYZE: {label} ===")

        print(
            "QUERY:",
            {
                "r_loops": query_block.get("r_loops"),
                "r_total_time_ms": query_block.get(
                    "r_total_time_ms"
                ),
            },
        )

        print_runtime_metrics(query_block)
