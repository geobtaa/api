import json
from datetime import date

import pytest

from scripts import update_monthly_analytics as monthly


def test_boundary_handles_year_and_leap_day():
    assert monthly.reporting_boundary(date(2027, 1, 1)) == date(2027, 1, 1)
    assert monthly.reporting_boundary(date(2028, 2, 29)) == date(2028, 2, 1)


def test_rejects_incomplete_or_noncalendar_boundary(tmp_path):
    for boundary in (date(2099, 1, 1), date(2026, 9, 15)):
        with pytest.raises(ValueError, match="Through"):
            monthly.update([], tmp_path / "counts.json", tmp_path, boundary)


def test_failed_projection_leaves_existing_publication_untouched(tmp_path, monkeypatch):
    data = tmp_path / "src/data/analytics"
    public = tmp_path / "private-analytics-reports"
    data.mkdir(parents=True)
    public.mkdir(parents=True)
    (data / "monthlySnapshots.json").write_text("original data")
    (public / "manifest.json").write_text("original manifest")

    def exported(archives, through, output, selected):
        output.mkdir()
        (output / "manifest.json").write_text(json.dumps({"periods": []}))

    monkeypatch.setattr(monthly, "export", exported)

    def fail(*args):
        raise ValueError("Supplemental search counts do not reconcile")

    monkeypatch.setattr(monthly, "run", fail)
    with pytest.raises(ValueError, match="do not reconcile"):
        monthly.update([], tmp_path / "counts.json", tmp_path, date(2026, 10, 1))
    assert (data / "monthlySnapshots.json").read_text() == "original data"
    assert (public / "manifest.json").read_text() == "original manifest"


def test_incomplete_new_month_cannot_replace_reports(tmp_path, monkeypatch):
    (tmp_path / "src/data/analytics").mkdir(parents=True)

    def exported(archives, through, output, selected):
        output.mkdir()
        (output / "manifest.json").write_text(
            json.dumps({"periods": [{"id": "2026-09", "complete": False}]})
        )

    monkeypatch.setattr(monthly, "export", exported)
    with pytest.raises(ValueError, match="Incomplete monthly source coverage"):
        monthly.update([], tmp_path / "counts.json", tmp_path, date(2026, 10, 1))
    assert not (tmp_path / "public").exists()
