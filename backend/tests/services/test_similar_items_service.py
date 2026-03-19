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

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_similar_items_use_bridge_thumbnail_when_available(self):
        """Bridge thumbnail-capable asset should be preferred over ImageService."""

        def make_row(resource_id: str, title: str):
            row = MagicMock()
            row._mapping = {
                "id": resource_id,
                "dct_title_s": title,
                "dct_temporal_sm": [],
                "gbl_indexYear_im": [2025],
                "gbl_resourceClass_sm": ["Datasets"],
            }
            return row

        # 1) resource lookup query -> rows via fetchall()
        resource_result = MagicMock()
        resource_result.fetchall.return_value = [make_row("similar-1", "Map of Now")]

        # 2) bridge thumbnail query -> scalar_one_or_none()
        thumb_result = MagicMock()
        thumb_result.scalar_one_or_none.return_value = (
            "https://geobtaa-assets-prod.s3.us-east-2.amazonaws.com/store/asset/thumb.png"
        )

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[resource_result, thumb_result])

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
            ) as mock_fetch_distribution_context,
            patch("app.services.similar_items_service.ImageService") as mock_image_svc,
        ):
            items = await SimilarItemsService.get_similar_items(
                "source-resource-id", mock_session, limit=12
            )

        assert len(items) == 1
        assert items[0]["id"] == "similar-1"
        assert "geobtaa-assets-prod.s3" in items[0]["thumbnail_url"]

        # When bridge thumbnail exists, we should not fall back to ImageService.
        mock_fetch_distribution_context.assert_not_called()
        mock_image_svc.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_similar_items_falls_back_to_imageservice_when_bridge_thumbnail_missing(
        self,
    ):
        """If no bridge thumbnail is available, use ImageService thumbnail_url."""

        def make_row(resource_id: str, title: str):
            row = MagicMock()
            row._mapping = {
                "id": resource_id,
                "dct_title_s": title,
                "dct_temporal_sm": [],
                "gbl_indexYear_im": [2025],
                "gbl_resourceClass_sm": ["Datasets"],
            }
            return row

        resource_result = MagicMock()
        resource_result.fetchall.return_value = [make_row("similar-1", "Map of Now")]

        thumb_result = MagicMock()
        thumb_result.scalar_one_or_none.return_value = None

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[resource_result, thumb_result])

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
            ) as mock_fetch_distribution_context,
            patch("app.services.similar_items_service.ImageService") as mock_image_svc,
        ):
            mock_image_svc.return_value.get_thumbnail_url.return_value = (
                "https://example.com/thumb.jpg"
            )

            items = await SimilarItemsService.get_similar_items(
                "source-resource-id", mock_session, limit=12
            )

        assert len(items) == 1
        assert items[0]["id"] == "similar-1"
        assert items[0]["thumbnail_url"] == "https://example.com/thumb.jpg"
        assert mock_fetch_distribution_context.called
        assert mock_image_svc.called
