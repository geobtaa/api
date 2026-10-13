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


def test_successful_refresh_installs_member_rankings(tmp_path, monkeypatch):
    data = tmp_path / "src/data/analytics"
    destination = tmp_path / "private-analytics-reports"
    data.mkdir(parents=True)
    destination.mkdir()
    (data / "memberLeadingContent.json").write_text('{"all": "old rankings"}')
    (data / "memberCollectionViews.json").write_text('{"all": "old collections"}')
    months = ["2026-07", "2026-08", "2026-09", "2026-10"]
    monkeypatch.setattr(monthly, "reporting_boundary", lambda: date(2026, 11, 1))

    def exported(archives, through, output, selected):
        output.mkdir()
        for period in selected:
            (output / period).mkdir()
        (output / "manifest.json").write_text(
            json.dumps(
                {
                    "latest": months[-1],
                    "periods": [{"id": m, "complete": True} for m in selected],
                }
            )
        )

    def projected(archives, public, output, supplemental, month):
        # Distinct sentinel rankings prove the generated output replaces old history.
        for name in (
            "popularHistory2026",
            "allTimeCurrent",
            "memberAllTimeCurrent",
            "outcomesCurrent",
            "collectionSearchesCurrent",
            "collectionViewsCurrent",
            "popularMomentumCurrent",
            "reliabilityEndpointsCurrent",
        ):
            (output / f"{name}.json").write_text("{}")
        (output / f"month-{month}.json").write_text(json.dumps({"month": month}))
        (output / "memberCollectionViews.json").write_text(
            json.dumps({month: {"12": [{"id": "collection", "views": 42}]}})
        )
        (output / "memberLeadingContent.json").write_text(
            json.dumps(
                {
                    "all": {"views": 99},
                    month: {"views": 12},
                }
            )
        )

    monkeypatch.setattr(monthly, "export", exported)
    monkeypatch.setattr(monthly, "run", projected)
    monthly.update([], tmp_path / "counts.json", tmp_path, date(2026, 11, 1))
    rankings = json.loads((data / "memberLeadingContent.json").read_text())
    assert rankings == {"all": {"views": 99}, "2026-10": {"views": 12}}
    assert json.loads((data / "memberCollectionViews.json").read_text()) == {
        "2026-10": {"12": [{"id": "collection", "views": 42}]}
    }
    assert json.loads((destination / "manifest.json").read_text())["latest"] == "2026-10"
    assert set(json.loads((data / "monthlySnapshots.json").read_text())) == set(months[2:])
