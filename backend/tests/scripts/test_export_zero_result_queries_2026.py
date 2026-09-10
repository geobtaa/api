"""Exercise aggregate SQL using an isolated in-memory fixture, without services."""

import pytest
from sqlalchemy import create_engine, text

from scripts import export_zero_result_queries_2026 as report


@pytest.fixture
def connection():
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.connection.driver_connection.create_function(
            "btrim", 1, lambda value: None if value is None else value.strip(" ")
        )
        connection.execute(
            text(
                "CREATE TABLE analytics_searches "
                "(query TEXT, zero_results BOOLEAN, occurred_at TEXT)"
            )
        )
        yield connection
    engine.dispose()


def insert(connection, query, zero=True, occurred="2026-08-01"):
    connection.execute(
        text("INSERT INTO analytics_searches VALUES (:query, :zero, :occurred)"),
        {"query": query, "zero": zero, "occurred": occurred},
    )


def test_top_100_includes_one_and_two_event_queries(connection, monkeypatch):
    for index in range(101):
        insert(connection, f"term-{index:03d}")
    insert(connection, " term-100 ")
    monkeypatch.setitem(
        report.EXPECTED,
        "2026-08",
        {"searches": 102, "zeroResults": 102, "withQuery": 102, "withoutQuery": 0},
    )
    result = report.export_month(connection, "2026-08")
    assert result["distinctQueries"] == 101
    assert len(result["zeroQueries"]) == 100
    assert result["zeroQueries"][0] == {"term": "term-100", "count": 2}
    assert result["zeroQueries"][-1] == {"term": "term-098", "count": 1}
    assert result["rankedZeroResults"] == 101


def test_month_bounds_blank_queries_case_and_nonzero_results(connection, monkeypatch):
    for query in (" Place ", "Place", "place", "", "   ", None):
        insert(connection, query)
    insert(connection, "successful", zero=False)
    insert(connection, "previous month", occurred="2026-07-31 23:59:59")
    insert(connection, "next month", occurred="2026-09-01")
    monkeypatch.setitem(
        report.EXPECTED,
        "2026-08",
        {"searches": 7, "zeroResults": 6, "withQuery": 3, "withoutQuery": 3},
    )
    result = report.export_month(connection, "2026-08")
    assert result["zeroQueries"] == [{"term": "Place", "count": 2}, {"term": "place", "count": 1}]
    assert result["distinctQueries"] == 2
    assert result["periodStart"] == "2026-08-01"
    assert result["periodEndExclusive"] == "2026-09-01"


def test_incomplete_history_is_rejected(connection):
    insert(connection, "partial history")
    with pytest.raises(ValueError, match="Incomplete or changed 2026-08 search history"):
        report.export_month(connection, "2026-08")
