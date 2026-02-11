"""Tests for SimilarItemsService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.similar_items_service import SimilarItemsService


class TestSimilarItemsServicePayload:
    """Test that similar items include gbl_indexYear_im and gbl_resourceClass_sm."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_similar_items_include_index_year_and_resource_class(self):
        """Similar items payload includes gbl_indexYear_im and gbl_resourceClass_sm."""

        # Create a row-like object with _mapping (simulates SQLAlchemy Row)
        def make_row(resource_id: str, title: str, index_year=None, resource_class=None):
            row = MagicMock()
            row._mapping = {
                "id": resource_id,
                "dct_title_s": title,
                "dct_temporal_sm": [],
                "gbl_indexYear_im": index_year or [1929],
                "gbl_resourceClass_sm": resource_class or ["Maps"],
            }
            return row

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            make_row("similar-1", "Map of France", [1929], ["Maps"]),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "app.services.similar_items_service.find_similar_resources",
                new_callable=AsyncMock,
                return_value=["similar-1"],
            ),
            patch(
                "app.services.similar_items_service.fetch_distribution_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.similar_items_service.ImageService",
            ) as mock_image_svc,
        ):
            mock_image_svc.return_value.get_thumbnail_url.return_value = (
                "https://example.com/thumb.jpg"
            )

            items = await SimilarItemsService.get_similar_items(
                "source-resource-id", mock_session, limit=12
            )

        assert len(items) == 1
        item = items[0]
        assert item["id"] == "similar-1"
        assert item["title"] == "Map of France"
        assert item["gbl_indexYear_im"] == [1929]
        assert item["gbl_resourceClass_sm"] == ["Maps"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_similar_items_handles_missing_index_year_and_resource_class(self):
        """Similar items handles missing gbl_indexYear_im and gbl_resourceClass_sm."""

        def make_row(resource_id: str, title: str):
            row = MagicMock()
            row._mapping = {
                "id": resource_id,
                "dct_title_s": title,
                "dct_temporal_sm": [],
                # No gbl_indexYear_im or gbl_resourceClass_sm
            }
            return row

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            make_row("no-meta-1", "Untitled Resource"),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "app.services.similar_items_service.find_similar_resources",
                new_callable=AsyncMock,
                return_value=["no-meta-1"],
            ),
            patch(
                "app.services.similar_items_service.fetch_distribution_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.similar_items_service.ImageService"),
        ):
            items = await SimilarItemsService.get_similar_items("source-id", mock_session, limit=12)

        assert len(items) == 1
        item = items[0]
        assert item["gbl_indexYear_im"] == []
        assert item["gbl_resourceClass_sm"] == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_similar_items_empty_when_no_similar_ids(self):
        """Returns empty list when find_similar_resources returns no IDs."""
        mock_session = MagicMock()

        with patch(
            "app.services.similar_items_service.find_similar_resources",
            new_callable=AsyncMock,
            return_value=[],
        ):
            items = await SimilarItemsService.get_similar_items("source-id", mock_session, limit=12)

        assert items == []
        mock_session.execute.assert_not_called()
