"""
Tests for the gazetteer base downloader module (app.gazetteer.downloaders.base_downloader).
"""

import pytest

import app.gazetteer.downloaders.base_downloader as downloader_module


class TestBaseDownloader:
    """Test cases for BaseDownloader class."""

    def test_base_downloader_class_exists(self):
        """Test that BaseDownloader class exists and can be imported."""
        assert downloader_module.BaseDownloader is not None

    def test_base_downloader_is_abstract(self):
        """Test that BaseDownloader is an abstract class."""
        from abc import ABC

        assert issubclass(downloader_module.BaseDownloader, ABC)

    def test_base_downloader_has_expected_methods(self):
        """Test that BaseDownloader has expected methods."""
        # Check that the class has expected methods
        assert hasattr(downloader_module.BaseDownloader, "__init__")
        assert hasattr(downloader_module.BaseDownloader, "ensure_directories")
        assert hasattr(downloader_module.BaseDownloader, "download")
        assert hasattr(downloader_module.BaseDownloader, "export")
        assert hasattr(downloader_module.BaseDownloader, "run")

    def test_base_downloader_methods_are_callable(self):
        """Test that BaseDownloader methods are callable."""
        # Check that methods exist and are callable
        assert callable(downloader_module.BaseDownloader.__init__)
        assert callable(downloader_module.BaseDownloader.ensure_directories)
        assert callable(downloader_module.BaseDownloader.download)
        assert callable(downloader_module.BaseDownloader.export)
        assert callable(downloader_module.BaseDownloader.run)

    def test_base_downloader_run_method_signature(self):
        """Test that run method has correct signature."""
        import inspect

        sig = inspect.signature(downloader_module.BaseDownloader.run)
        params = list(sig.parameters.keys())

        # Should have expected parameters
        assert "download" in params
        assert "export" in params
        assert "all" in params

    def test_base_downloader_init_signature(self):
        """Test that __init__ method has correct signature."""
        import inspect

        sig = inspect.signature(downloader_module.BaseDownloader.__init__)
        params = list(sig.parameters.keys())

        # Should have expected parameters
        assert "self" in params
        assert "data_dir" in params
        assert "gazetteer_name" in params


class TestBaseDownloaderModuleStructure:
    """Test cases for module structure and imports."""

    def test_module_imports(self):
        """Test that required modules can be imported."""
        try:
            assert downloader_module.BaseDownloader is not None
            assert downloader_module.logger is not None
        except ImportError as e:
            pytest.skip(f"Required dependency not available: {e}")

    def test_logger_configuration(self):
        """Test that logger is properly configured."""
        assert downloader_module.logger is not None
        assert hasattr(downloader_module.logger, "name")

    def test_module_docstring(self):
        """Test that module has proper docstring."""

        assert downloader_module.__doc__ is not None
        assert len(downloader_module.__doc__.strip()) > 0

    def test_module_version_info(self):
        """Test that module has basic structure."""

        assert hasattr(downloader_module, "BaseDownloader")
        assert hasattr(downloader_module, "logger")

    def test_required_imports(self):
        """Test that required imports are available."""

        # Check for required imports
        required_attributes = ["BaseDownloader", "logger"]
        for attr in required_attributes:
            assert hasattr(downloader_module, attr), f"Missing {attr} in module"

    def test_abstract_methods_exist(self):
        """Test that abstract methods exist on the class."""
        # Check that abstract methods exist
        assert hasattr(downloader_module.BaseDownloader, "download")
        assert hasattr(downloader_module.BaseDownloader, "export")

        # Check that they are abstract methods
        assert hasattr(downloader_module.BaseDownloader.download, "__isabstractmethod__")
        assert hasattr(downloader_module.BaseDownloader.export, "__isabstractmethod__")

    def test_class_inheritance(self):
        """Test that BaseDownloader inherits from ABC."""
        from abc import ABC

        assert issubclass(downloader_module.BaseDownloader, ABC)

    def test_module_has_required_imports(self):
        """Test that module has required imports."""

        # Should have required imports
        assert hasattr(downloader_module, "logging")
        assert hasattr(downloader_module, "ABC")
        assert hasattr(downloader_module, "abstractmethod")
        assert hasattr(downloader_module, "datetime")
        assert hasattr(downloader_module, "Path")
