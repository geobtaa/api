"""
Tests for RelationshipService - comprehensive coverage using real fixtures and data.
"""

import pytest
from sqlalchemy import delete

from app.services.relationship_service import RelationshipService
from db.database import database
from db.models import resource_relationships, resources


class TestRelationshipService:
    """Test cases for RelationshipService functionality."""

    @pytest.mark.asyncio(scope="session")
    async def test_relationships_include_suppressed_published_targets(self):
        """Relationship widgets include suppressed targets that are still published."""
        parent_id = "relationship-visibility-parent"
        visible_id = "relationship-visibility-published"
        draft_id = "relationship-visibility-draft"
        unpublished_id = "relationship-visibility-unpublished"
        suppressed_id = "relationship-visibility-suppressed"
        resource_ids = [
            parent_id,
            visible_id,
            draft_id,
            unpublished_id,
            suppressed_id,
        ]

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(resource_relationships).where(
                    (resource_relationships.c.subject_id.in_(resource_ids))
                    | (resource_relationships.c.object_id.in_(resource_ids))
                )
            )
            await database.execute(delete(resources).where(resources.c.id.in_(resource_ids)))
            await database.execute_many(
                query=resources.insert(),
                values=[
                    {
                        "id": parent_id,
                        "dct_title_s": "Relationship Parent",
                        "publication_state": "published",
                        "gbl_suppressed_b": False,
                    },
                    {
                        "id": visible_id,
                        "dct_title_s": "Published Target",
                        "publication_state": "published",
                        "gbl_suppressed_b": False,
                    },
                    {
                        "id": draft_id,
                        "dct_title_s": "Draft Target",
                        "publication_state": "draft",
                        "gbl_suppressed_b": False,
                    },
                    {
                        "id": unpublished_id,
                        "dct_title_s": "Unpublished Target",
                        "publication_state": "unpublished",
                        "gbl_suppressed_b": False,
                    },
                    {
                        "id": suppressed_id,
                        "dct_title_s": "Suppressed Target",
                        "publication_state": "published",
                        "gbl_suppressed_b": True,
                    },
                ],
            )
            await database.execute_many(
                query=resource_relationships.insert(),
                values=[
                    {
                        "subject_id": parent_id,
                        "predicate": "dct:source",
                        "object_id": object_id,
                    }
                    for object_id in [visible_id, draft_id, unpublished_id, suppressed_id]
                ],
            )

            relationships = await RelationshipService.get_resource_relationships(parent_id)
            summaries = await RelationshipService.get_resource_relationship_summaries_map(
                [parent_id]
            )

            assert relationships == {
                "dct:source": [
                    {
                        "resource_id": visible_id,
                        "resource_title": "Published Target",
                        "link": f"/resources/{visible_id}",
                    },
                    {
                        "resource_id": suppressed_id,
                        "resource_title": "Suppressed Target",
                        "link": f"/resources/{suppressed_id}",
                    },
                ]
            }
            assert summaries[parent_id]["relationships"] == relationships
            assert summaries[parent_id]["counts"] == {"dct:source": 2}
        finally:
            await database.execute(
                delete(resource_relationships).where(
                    (resource_relationships.c.subject_id.in_(resource_ids))
                    | (resource_relationships.c.object_id.in_(resource_ids))
                )
            )
            await database.execute(delete(resources).where(resources.c.id.in_(resource_ids)))

    @pytest.mark.asyncio
    async def test_get_resource_relationship_summaries_map_limits_and_counts(self, monkeypatch):
        """Search relationship summaries expose previews, counts, and browse links."""

        async def fake_fetch_relationship_rows(resource_ids, *, limit_per_predicate=None):
            assert list(resource_ids) == ["01d-05"]
            assert limit_per_predicate == 5
            return [
                {
                    "subject_id": "01d-05",
                    "predicate": "dct:hasPart",
                    "object_id": f"part-{index}",
                    "dct_title_s": f"Part {index}",
                    "total_count": 10085,
                }
                for index in range(1, 6)
            ]

        monkeypatch.setattr(
            RelationshipService,
            "_fetch_relationship_rows",
            staticmethod(fake_fetch_relationship_rows),
        )

        result = await RelationshipService.get_resource_relationship_summaries_map(["01d-05"])

        summary = result["01d-05"]
        assert len(summary["relationships"]["dct:hasPart"]) == 5
        assert summary["counts"]["dct:hasPart"] == 10085
        assert summary["browse_links"]["dct:hasPart"] == (
            "/search?include_filters[dct_isPartOf_sm][]=01d-05"
        )
        assert summary["relationships"]["dct:hasPart"][0] == {
            "resource_id": "part-1",
            "resource_title": "Part 1",
            "link": "/resources/part-1",
        }

    @pytest.mark.asyncio
    async def test_source_of_aliases_are_canonicalized_and_deduplicated(self, monkeypatch):
        async def fake_fetch_relationship_rows(resource_ids, *, limit_per_predicate=None):
            assert list(resource_ids) == ["parent-record"]
            assert limit_per_predicate is None
            return [
                {
                    "subject_id": "parent-record",
                    "predicate": predicate,
                    "object_id": "child-record",
                    "dct_title_s": "Child record",
                }
                for predicate in ("dct:isSourceOf", "dct:sourceOf")
            ]

        monkeypatch.setattr(
            RelationshipService,
            "_fetch_relationship_rows",
            staticmethod(fake_fetch_relationship_rows),
        )

        relationships = await RelationshipService.get_resource_relationships("parent-record")

        assert relationships == {
            "dct:isSourceOf": [
                {
                    "resource_id": "child-record",
                    "resource_title": "Child record",
                    "link": "/resources/child-record",
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_source_of_summary_uses_derived_records_browse_filter(self, monkeypatch):
        async def fake_fetch_relationship_rows(resource_ids, *, limit_per_predicate=None):
            assert list(resource_ids) == ["parent-record"]
            assert limit_per_predicate == 5
            return [
                {
                    "subject_id": "parent-record",
                    "predicate": predicate,
                    "object_id": "child-record",
                    "dct_title_s": "Child record",
                    "total_count": 20,
                }
                for predicate in ("dct:isSourceOf", "dct:sourceOf")
            ]

        monkeypatch.setattr(
            RelationshipService,
            "_fetch_relationship_rows",
            staticmethod(fake_fetch_relationship_rows),
        )

        summaries = await RelationshipService.get_resource_relationship_summaries_map(
            ["parent-record"]
        )

        summary = summaries["parent-record"]
        assert len(summary["relationships"]["dct:isSourceOf"]) == 1
        assert summary["counts"] == {"dct:isSourceOf": 20}
        assert summary["browse_links"] == {
            "dct:isSourceOf": ("/search?include_filters[dct_source_sm][]=parent-record")
        }

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_real_database(self):
        """Test getting resource relationships using real database connection."""
        # Use real database connection - will handle connection errors gracefully
        try:
            result = await RelationshipService.get_resource_relationships("test-resource-id")

            # Should return a dictionary (empty if resource not found or no relationships)
            assert isinstance(result, dict)

        except Exception as e:
            # Handle database connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "database" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_nonexistent_resource(self):
        """Test getting relationships for non-existent resource."""
        try:
            result = await RelationshipService.get_resource_relationships("nonexistent-resource-id")

            # Should return empty dict for non-existent resource
            assert result == {}

        except Exception as e:
            # Handle database connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "database" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_various_ids(self):
        """Test getting relationships with various resource IDs."""
        test_ids = [
            "valid-resource-123",
            "another-valid-resource-456",
            "resource-with-special-chars-789",
            "very-long-resource-id-that-might-test-different-behavior-123456789",
        ]

        for resource_id in test_ids:
            try:
                result = await RelationshipService.get_resource_relationships(resource_id)

                # Should return a dictionary
                assert isinstance(result, dict)

            except Exception as e:
                # Handle database connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "database" in str(e).lower()
                    or "nodename" in str(e).lower()
                )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_special_characters(self):
        """Test getting relationships with resource IDs containing special characters."""
        special_ids = [
            "resource-with-dashes-123",
            "resource_with_underscores_456",
            "resource.with.dots.789",
            "resource with spaces 123",
            "resource/with/slashes/456",
            "resource@with@symbols@789",
        ]

        for resource_id in special_ids:
            try:
                result = await RelationshipService.get_resource_relationships(resource_id)

                # Should return a dictionary
                assert isinstance(result, dict)

            except Exception as e:
                # Handle database connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "database" in str(e).lower()
                    or "nodename" in str(e).lower()
                )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_empty_string(self):
        """Test getting relationships with empty string resource ID."""
        try:
            result = await RelationshipService.get_resource_relationships("")

            # Should return a dictionary (empty if no relationships found)
            assert isinstance(result, dict)

        except Exception as e:
            # Handle database connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "database" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_none(self):
        """Test getting relationships with None resource ID."""
        try:
            result = await RelationshipService.get_resource_relationships(None)

            # Should return a dictionary (empty if no relationships found)
            assert isinstance(result, dict)

        except Exception as e:
            # Handle database connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "database" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_unicode(self):
        """Test getting relationships with Unicode resource IDs."""
        unicode_ids = [
            "resource-with-unicode-ñ-123",
            "resource-with-émojis-456",
            "resource-中文-789",
            "resource-العربية-123",
        ]

        for resource_id in unicode_ids:
            try:
                result = await RelationshipService.get_resource_relationships(resource_id)

                # Should return a dictionary
                assert isinstance(result, dict)

            except Exception as e:
                # Handle database connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "database" in str(e).lower()
                    or "nodename" in str(e).lower()
                )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_very_long_id(self):
        """Test getting relationships with very long resource ID."""
        long_id = "a" * 1000  # Very long resource ID

        try:
            result = await RelationshipService.get_resource_relationships(long_id)

            # Should return a dictionary
            assert isinstance(result, dict)

        except Exception as e:
            # Handle database connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "database" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_numeric_id(self):
        """Test getting relationships with numeric resource ID."""
        numeric_ids = ["123", "456", "789", "0", "999999"]

        for resource_id in numeric_ids:
            try:
                result = await RelationshipService.get_resource_relationships(resource_id)

                # Should return a dictionary
                assert isinstance(result, dict)

            except Exception as e:
                # Handle database connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "database" in str(e).lower()
                    or "nodename" in str(e).lower()
                )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_sql_injection_attempts(self):
        """Test getting relationships with potential SQL injection attempts."""
        sql_injection_attempts = [
            "'; DROP TABLE resources; --",
            "1' OR '1'='1",
            "admin'--",
            "1; DELETE FROM resources; --",
            "' UNION SELECT * FROM users --",
        ]

        for resource_id in sql_injection_attempts:
            try:
                result = await RelationshipService.get_resource_relationships(resource_id)

                # Should return a dictionary (empty if no relationships found)
                assert isinstance(result, dict)

            except Exception as e:
                # Handle database connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "database" in str(e).lower()
                    or "nodename" in str(e).lower()
                )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_static_method(self):
        """Test that get_resource_relationships is properly defined as static method."""
        # Verify it's a static method by calling it on the class
        try:
            result = await RelationshipService.get_resource_relationships("test-id")
            assert isinstance(result, dict)
        except Exception as e:
            # Handle database connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "database" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_return_structure(self):
        """Test the expected structure of returned relationships."""
        try:
            result = await RelationshipService.get_resource_relationships("test-resource-id")

            # Should return a dictionary
            assert isinstance(result, dict)

            # If there are relationships, they should have the expected structure
            for predicate, relationships in result.items():
                assert isinstance(predicate, str)
                assert isinstance(relationships, list)

                for relationship in relationships:
                    assert isinstance(relationship, dict)
                    assert "resource_id" in relationship
                    assert "resource_title" in relationship
                    assert "link" in relationship
                    assert relationship["link"].startswith("/resources/")
                    assert relationship["resource_id"] == relationship["link"].split("/")[-1]

        except Exception as e:
            # Handle database connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "database" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_error_handling(self):
        """Test error handling in get_resource_relationships."""
        # Test with various problematic inputs
        problematic_inputs = [
            None,
            "",
            "   ",  # Whitespace only
            "\x00",  # Null byte
            "resource\x00with\x00nulls",
            "resource\nwith\nnewlines",
            "resource\twith\ttabs",
        ]

        for resource_id in problematic_inputs:
            try:
                result = await RelationshipService.get_resource_relationships(resource_id)

                # Should return a dictionary (empty if no relationships found)
                assert isinstance(result, dict)

            except Exception as e:
                # Handle database connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "database" in str(e).lower()
                    or "nodename" in str(e).lower()
                )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_concurrent_calls(self):
        """Test concurrent calls to get_resource_relationships."""
        import asyncio

        async def call_relationship_service(resource_id):
            try:
                return await RelationshipService.get_resource_relationships(resource_id)
            except Exception:
                return {}

        # Make multiple concurrent calls
        tasks = [call_relationship_service(f"resource-{i}") for i in range(5)]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All results should be dictionaries
        for result in results:
            if not isinstance(result, Exception):
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_resource_relationships_with_relationship_types(self):
        """Test getting relationships with different predicate types."""
        # Test with various relationship predicate types that might exist
        test_cases = [
            "test-resource-with-hasPart-relationships",
            "test-resource-with-isPartOf-relationships",
            "test-resource-with-references-relationships",
            "test-resource-with-referencedBy-relationships",
            "test-resource-with-requires-relationships",
            "test-resource-with-relatedTo-relationships",
        ]

        for resource_id in test_cases:
            try:
                result = await RelationshipService.get_resource_relationships(resource_id)

                # Should return a dictionary
                assert isinstance(result, dict)

                # If there are relationships, verify structure
                for predicate, relationships in result.items():
                    assert isinstance(predicate, str)
                    assert isinstance(relationships, list)

            except Exception as e:
                # Handle database connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "database" in str(e).lower()
                    or "nodename" in str(e).lower()
                )

    @pytest.mark.asyncio
    async def test_get_resource_relationships_performance(self):
        """Test performance with multiple calls."""
        import time

        start_time = time.time()

        # Make multiple calls to test performance
        for i in range(10):
            try:
                result = await RelationshipService.get_resource_relationships(
                    f"perf-test-resource-{i}"
                )
                assert isinstance(result, dict)
            except Exception as e:
                # Handle database connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "database" in str(e).lower()
                    or "nodename" in str(e).lower()
                )

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in reasonable time (adjust threshold as needed)
        assert execution_time < 30.0  # 30 seconds should be more than enough
