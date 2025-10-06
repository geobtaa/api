"""
Tests for the summarization task module.
"""

import json
from datetime import datetime

import pytest

from app.tasks.summarization import DateTimeEncoder


class TestDateTimeEncoder:
    """Test cases for DateTimeEncoder."""

    def test_datetime_encoding(self):
        """Test encoding datetime objects."""
        encoder = DateTimeEncoder()

        test_datetime = datetime(2023, 1, 1, 12, 30, 45)
        result = encoder.default(test_datetime)

        assert result == "2023-01-01T12:30:45"

    def test_non_datetime_encoding(self):
        """Test encoding non-datetime objects."""
        encoder = DateTimeEncoder()

        # Test that non-datetime objects raise TypeError
        with pytest.raises(TypeError):
            encoder.default(123)

        with pytest.raises(TypeError):
            encoder.default("test_string")

        with pytest.raises(TypeError):
            encoder.default({"key": "value"})

    def test_json_dumps_with_datetime(self):
        """Test json.dumps with DateTimeEncoder."""
        test_data = {"timestamp": datetime(2023, 1, 1, 12, 30, 45), "message": "test"}

        result = json.dumps(test_data, cls=DateTimeEncoder)
        expected = '{"timestamp": "2023-01-01T12:30:45", "message": "test"}'

        assert result == expected

    def test_json_dumps_without_datetime(self):
        """Test json.dumps with DateTimeEncoder when no datetime objects."""
        test_data = {"message": "test", "number": 123}

        result = json.dumps(test_data, cls=DateTimeEncoder)
        expected = '{"message": "test", "number": 123}'

        assert result == expected


class TestSummarizationTaskStructure:
    """Test cases for task structure and imports."""

    def test_task_imports(self):
        """Test that required modules can be imported."""
        try:
            from celery import shared_task

            from app.tasks.summarization import (
                _generate_summary,
                generate_resource_summary,
                store_summary_in_db,
            )

            # If we get here, imports succeeded
            assert generate_resource_summary is not None
            assert _generate_summary is not None
            assert store_summary_in_db is not None
        except ImportError as e:
            pytest.skip(f"Required dependency not available: {e}")

    def test_task_decorator_presence(self):
        """Test that the task function has the shared_task decorator."""
        from app.tasks.summarization import generate_resource_summary

        # Check if the function has Celery task attributes
        assert hasattr(generate_resource_summary, "delay")
        assert hasattr(generate_resource_summary, "apply_async")

    def test_task_function_signature(self):
        """Test the task function signature."""
        import inspect

        from app.tasks.summarization import generate_resource_summary

        sig = inspect.signature(generate_resource_summary)
        params = list(sig.parameters.keys())

        expected_params = ["resource_id", "metadata", "asset_path", "asset_type"]
        assert params == expected_params

    def test_task_default_values(self):
        """Test the default values for optional parameters."""
        import inspect

        from app.tasks.summarization import generate_resource_summary

        sig = inspect.signature(generate_resource_summary)

        # Check default values
        assert sig.parameters["asset_path"].default is None
        assert sig.parameters["asset_type"].default is None

    def test_logger_initialization(self):
        """Test that logger is properly initialized."""
        from app.tasks.summarization import logger

        assert logger is not None
        assert logger.name == "app.tasks.summarization"

    def test_async_function_signature(self):
        """Test the async function signature."""
        import inspect

        from app.tasks.summarization import _generate_summary

        # Check that the function is async
        assert inspect.iscoroutinefunction(_generate_summary)

        # Check parameter defaults
        sig = inspect.signature(_generate_summary)
        assert sig.parameters["asset_path"].default is None
        assert sig.parameters["asset_type"].default is None

    def test_store_function_signature(self):
        """Test the store function signature."""
        import inspect

        from app.tasks.summarization import store_summary_in_db

        # Check that the function is async
        assert inspect.iscoroutinefunction(store_summary_in_db)

        # Check parameters
        sig = inspect.signature(store_summary_in_db)
        params = list(sig.parameters.keys())

        expected_params = ["resource_id", "model", "summary", "prompt", "output_parser"]
        assert params == expected_params

    def test_datetime_encoder_class(self):
        """Test that DateTimeEncoder is properly defined."""
        from app.tasks.summarization import DateTimeEncoder

        assert DateTimeEncoder is not None
        assert issubclass(DateTimeEncoder, json.JSONEncoder)

        # Test that it can be instantiated
        encoder = DateTimeEncoder()
        assert encoder is not None
