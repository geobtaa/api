"""Unit tests for _compute_h3_cells (H3 pyramid indexing)."""

import pytest

pytest.importorskip("h3")

from app.elasticsearch.index import (
    _compute_h3_cells,
    CENTROID_MAX_DIAGONAL_KM,
    H3_PYRAMID_RESOLUTIONS,
    NEAR_GLOBAL_DIAGONAL_KM,
)


class TestComputeH3Cells:
    def test_geo_global_skips_h3_sets_geo_or_near_global(self):
        d = {
            "geo_global": True,
            "bbox_diagonal_km": 100,
            "dcat_centroid": [-93.2, 44.9],
        }
        _compute_h3_cells(d)
        assert d["geo_or_near_global"] is True
        for r in H3_PYRAMID_RESOLUTIONS:
            assert f"h3_res{r}" not in d

    def test_near_global_diagonal_skips_h3_sets_geo_or_near_global(self):
        d = {
            "geo_global": False,
            "bbox_diagonal_km": NEAR_GLOBAL_DIAGONAL_KM + 1,
            "dcat_centroid": [-93.2, 44.9],
        }
        _compute_h3_cells(d)
        assert d["geo_or_near_global"] is True
        for r in H3_PYRAMID_RESOLUTIONS:
            assert f"h3_res{r}" not in d

    def test_large_diagonal_over_500_sets_h3_when_under_near_global(self):
        """Diagonal > 500 km but < 15_000 km gets H3 from centroid (no 500 km cap)."""
        d = {
            "geo_global": False,
            "bbox_diagonal_km": CENTROID_MAX_DIAGONAL_KM + 100,
            "dcat_centroid": [-93.2, 44.9],
        }
        _compute_h3_cells(d)
        assert d["geo_or_near_global"] is False
        for r in H3_PYRAMID_RESOLUTIONS:
            assert f"h3_res{r}" in d
            assert isinstance(d[f"h3_res{r}"], str)

    def test_no_centroid_skips_h3(self):
        d = {
            "geo_global": False,
            "bbox_diagonal_km": 100,
        }
        _compute_h3_cells(d)
        assert d["geo_or_near_global"] is False
        for r in H3_PYRAMID_RESOLUTIONS:
            assert f"h3_res{r}" not in d

    def test_no_diagonal_centroid_only_sets_h3(self):
        """Centroid-only (no bbox) gets H3 when not geo_global."""
        d = {
            "geo_global": False,
            "dcat_centroid": [-93.2, 44.9],
        }
        _compute_h3_cells(d)
        assert d["geo_or_near_global"] is False
        for r in H3_PYRAMID_RESOLUTIONS:
            assert f"h3_res{r}" in d
            assert isinstance(d[f"h3_res{r}"], str)

    def test_valid_centroid_small_diagonal_sets_h3_and_geo_or_near_global_false(self):
        d = {
            "geo_global": False,
            "bbox_diagonal_km": 200,
            "dcat_centroid": [-93.2, 44.9],
        }
        _compute_h3_cells(d)
        assert d["geo_or_near_global"] is False
        for r in H3_PYRAMID_RESOLUTIONS:
            assert f"h3_res{r}" in d
            assert isinstance(d[f"h3_res{r}"], str)
            assert len(d[f"h3_res{r}"]) >= 10

    def test_diagonal_500_inclusive_sets_h3(self):
        d = {
            "geo_global": False,
            "bbox_diagonal_km": CENTROID_MAX_DIAGONAL_KM,
            "dcat_centroid": [-93.2, 44.9],
        }
        _compute_h3_cells(d)
        assert d["geo_or_near_global"] is False
        for r in H3_PYRAMID_RESOLUTIONS:
            assert f"h3_res{r}" in d

    def test_invalid_centroid_skips_h3(self):
        d = {
            "geo_global": False,
            "bbox_diagonal_km": 100,
            "dcat_centroid": "not-a-list",
        }
        _compute_h3_cells(d)
        for r in H3_PYRAMID_RESOLUTIONS:
            assert f"h3_res{r}" not in d

        d2 = {
            "geo_global": False,
            "bbox_diagonal_km": 100,
            "dcat_centroid": [1],
        }
        _compute_h3_cells(d2)
        for r in H3_PYRAMID_RESOLUTIONS:
            assert f"h3_res{r}" not in d2
