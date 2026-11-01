import duckdb
import pytest

from app.services.preview_assets.io import Budget
from app.services.preview_assets.models import Limits
from app.services.preview_assets.tabular import convert, prepare_table


def test_csv_preserves_identifiers_quotes_and_null(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text('id,name,value\n00123,"O\'Brien, Inc.",1.000\n00456,,9007199254740993\n')
    output, meta = prepare_table(source, Budget(Limits(), tmp_path))
    with duckdb.connect() as db:
        rows = db.read_parquet(str(output)).fetchall()
    assert rows == [("00123", "O'Brien, Inc.", "1.000"), ("00456", None, "9007199254740993")]
    assert meta["row_count"] == 2
    assert all(column["type"] == "VARCHAR" for column in meta["columns"])


def test_parquet_preserves_bigint_and_decimal(tmp_path):
    source = tmp_path / "source.parquet"
    with duckdb.connect() as db:
        db.sql(
            "SELECT 9007199254740993::BIGINT AS id, 1.23::DECIMAL(18,2) AS amount"
        ).write_parquet(str(source))
    output, meta = prepare_table(source, Budget(Limits(), tmp_path))
    with duckdb.connect() as db:
        assert db.read_parquet(str(source)).fetchall() == db.read_parquet(str(output)).fetchall()
    assert meta["columns"] == [
        {"name": "id", "type": "BIGINT"},
        {"name": "amount", "type": "DECIMAL(18,2)"},
    ]


def test_tsv_and_empty_rows(tmp_path):
    source = tmp_path / "source.tsv"
    source.write_text("id\tname\n001\tExample\n")
    output, meta = prepare_table(source, Budget(Limits(), tmp_path))
    assert meta["row_count"] == 1
    assert output.exists()


def test_malformed_csv_is_not_silently_truncated(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("id,name\n1,one,extra\n2,two\n")
    with pytest.raises(duckdb.InvalidInputException):
        convert(source, tmp_path / "out.parquet", tmp_path / "schema.json")


def test_nested_parquet_rejected(tmp_path):
    source = tmp_path / "source.parquet"
    with duckdb.connect() as db:
        db.sql("SELECT [1,2] AS nested").write_parquet(str(source))
    with pytest.raises(ValueError, match="Nested"):
        convert(source, tmp_path / "out.parquet", tmp_path / "schema.json")


def test_pipeline_publishes_table_without_inventing_map_or_thumbnail(tmp_path):
    import shutil

    from app.services.preview_assets.pipeline import Pipeline
    from app.services.preview_assets.sources import Source
    from app.services.preview_assets.storage import MIME, LocalStorage, check_key

    source = tmp_path / "source.csv"
    source.write_text("id,value\n00123,1\n")

    def fetch(url, target, budget):
        budget.read(source.stat().st_size)
        shutil.copyfile(source, target)
        return "a" * 64

    store = LocalStorage(tmp_path / "store")
    result = Pipeline(store, fetch=fetch).prepare(
        {"id": "table", "dct_accessRights_s": "Public"},
        source=Source("https://example.org/table.csv", "download"),
    )
    assert result.status.value == "ready", result.detail
    layer = result.layers[0]
    assert layer.format == "parquet"
    assert layer.row_count == 1
    assert layer.bounds is None
    assert result.thumbnail_status.value == "unsupported"
    assert store.path(layer.asset_key).is_file()
    check_key(layer.asset_key)
    assert MIME[".parquet"] == "application/vnd.apache.parquet"


@pytest.mark.parametrize("header", ["id,id", "id,ID", "id,"])
def test_ambiguous_headers_are_rejected(tmp_path, header):
    source = tmp_path / "source.csv"
    source.write_text(header + "\n1,2\n")
    with pytest.raises(ValueError, match="column names"):
        convert(source, tmp_path / "out.parquet", tmp_path / "schema.json")
