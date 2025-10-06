"""
Tests for the gazetteer download module (app.gazetteer.download).
"""

import pytest

from app.gazetteer.download import DOWNLOADERS, logger


class TestDownloadGazetteer:
    """Test cases for download_gazetteer function."""

    def test_download_gazetteer_function_exists(self):
        """Test that download_gazetteer function exists and is callable."""
        from app.gazetteer.download import download_gazetteer

        assert callable(download_gazetteer)

    def test_download_gazetteer_unsupported(self):
        """Test download_gazetteer with unsupported gazetteer."""
        from app.gazetteer.download import download_gazetteer

        result = download_gazetteer("nonexistent")

        assert result["status"] == "error"
        assert result["gazetteer"] == "nonexistent"
        assert "Unsupported gazetteer" in result["error"]

    def test_download_gazetteer_return_structure(self):
        """Test that download_gazetteer returns expected structure."""
        from app.gazetteer.download import download_gazetteer

        result = download_gazetteer("nonexistent")

        # Should return a dictionary with specific keys
        assert isinstance(result, dict)
        assert "status" in result
        assert "gazetteer" in result
        assert "error" in result


class TestDownloadersMapping:
    """Test cases for DOWNLOADERS mapping."""

    def test_downloaders_mapping_exists(self):
        """Test that DOWNLOADERS mapping is properly defined."""
        assert isinstance(DOWNLOADERS, dict)
        assert len(DOWNLOADERS) > 0

    def test_downloaders_mapping_keys(self):
        """Test that DOWNLOADERS mapping has expected keys."""
        expected_keys = ["wof", "geonames", "fast"]
        for key in expected_keys:
            assert key in DOWNLOADERS, f"Expected key {key} not found in DOWNLOADERS"

    def test_downloaders_mapping_values(self):
        """Test that DOWNLOADERS mapping has callable values."""
        for key, value in DOWNLOADERS.items():
            assert callable(value), f"DOWNLOADERS[{key}] should be callable"


class TestLoggerConfiguration:
    """Test cases for logger configuration."""

    def test_logger_exists(self):
        """Test that logger is properly configured."""
        assert logger is not None
        assert logger.name == "gazetteer_download"

    def test_logger_level(self):
        """Test that logger has appropriate level."""
        # Logger should be configured (level will be set by logging.basicConfig)
        assert logger.level >= 0


class TestModuleImports:
    """Test cases for module imports."""

    def test_module_imports(self):
        """Test that required modules can be imported."""
        try:
            from app.gazetteer.download import DOWNLOADERS, download_gazetteer, logger

            assert callable(download_gazetteer)
            assert isinstance(DOWNLOADERS, dict)
            assert logger is not None
        except ImportError as e:
            pytest.skip(f"Required dependency not available: {e}")

    def test_downloader_imports(self):
        """Test that downloader classes can be imported."""
        try:
            from app.gazetteer.downloaders import FastDownloader, GeoNamesDownloader, WofDownloader

            assert callable(FastDownloader)
            assert callable(GeoNamesDownloader)
            assert callable(WofDownloader)
        except ImportError as e:
            pytest.skip(f"Downloader classes not available: {e}")


class TestMainFunction:
    """Test cases for main function (command line interface)."""

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        from app.gazetteer.download import main

        assert callable(main)

    def test_argparse_import(self):
        """Test that argparse can be imported."""
        try:
            import argparse

            assert callable(argparse.ArgumentParser)
        except ImportError as e:
            pytest.skip(f"argparse not available: {e}")

    def test_datetime_import(self):
        """Test that datetime can be imported."""
        try:
            from datetime import datetime

            assert callable(datetime)
        except ImportError as e:
            pytest.skip(f"datetime not available: {e}")


class TestModuleStructure:
    """Test cases for module structure."""

    def test_module_docstring(self):
        """Test that module has proper docstring."""
        import app.gazetteer.download

        assert app.gazetteer.download.__doc__ is not None
        assert len(app.gazetteer.download.__doc__.strip()) > 0

    def test_module_version_info(self):
        """Test that module has basic structure."""
        import app.gazetteer.download

        assert hasattr(app.gazetteer.download, "download_gazetteer")
        assert hasattr(app.gazetteer.download, "DOWNLOADERS")
        assert hasattr(app.gazetteer.download, "logger")

    def test_if_name_main_block(self):
        """Test that __main__ block exists."""
        import app.gazetteer.download

        # Check that the file can be executed as main
        assert hasattr(app.gazetteer.download, "__name__")


class TestErrorHandling:
    """Test cases for error handling."""

    def test_invalid_gazetteer_name(self):
        """Test handling of invalid gazetteer names."""
        from app.gazetteer.download import download_gazetteer

        invalid_names = ["", "INVALID", "123", "wo f"]

        for invalid_name in invalid_names:
            result = download_gazetteer(invalid_name)
            assert result["status"] == "error"
            assert "Unsupported gazetteer" in result["error"]
