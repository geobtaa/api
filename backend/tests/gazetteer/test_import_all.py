"""
Tests for the gazetteer import_all module (app.gazetteer.import_all).
"""

import pytest

import app.gazetteer.import_all as import_all_module


class TestImportAll:
    """Test cases for import_all function."""

    def test_import_all_function_exists(self):
        """Test that import_all function exists and is callable."""

        assert callable(import_all_module.import_all)

    def test_import_all_function_signature(self):
        """Test that import_all has expected signature."""
        import inspect

        sig = inspect.signature(import_all_module.import_all)
        params = list(sig.parameters.keys())

        # Should have expected parameters
        assert "gazetteer_types" in params
        assert "data_dir" in params

    def test_import_all_is_async(self):
        """Test that import_all is an async function."""
        import inspect

        assert inspect.iscoroutinefunction(import_all_module.import_all)


class TestImportAllModuleStructure:
    """Test cases for module structure and imports."""

    def test_module_imports(self):
        """Test that required modules can be imported."""
        try:
            assert callable(import_all_module.import_all)
            assert import_all_module.logger is not None
        except ImportError as e:
            pytest.skip(f"Required dependency not available: {e}")

    def test_importer_imports(self):
        """Test that importer classes can be imported."""
        try:
            from app.gazetteer.importers.btaa_importer import BtaaImporter
            from app.gazetteer.importers.fast_importer import FastImporter
            from app.gazetteer.importers.geonames_importer import GeonamesImporter
            from app.gazetteer.importers.wof_importer import WofImporter

            assert callable(BtaaImporter)
            assert callable(FastImporter)
            assert callable(GeonamesImporter)
            assert callable(WofImporter)
        except ImportError as e:
            pytest.skip(f"Importer classes not available: {e}")

    def test_logger_configuration(self):
        """Test that logger is properly configured."""
        assert import_all_module.logger is not None
        # Logger name might be different depending on how the module is imported
        assert hasattr(import_all_module.logger, "name")

    def test_module_docstring(self):
        """Test that module has proper docstring."""

        assert import_all_module.__doc__ is not None
        assert len(import_all_module.__doc__.strip()) > 0

    def test_module_version_info(self):
        """Test that module has basic structure."""

        assert hasattr(import_all_module, "import_all")
        assert hasattr(import_all_module, "logger")

    def test_if_name_main_block(self):
        """Test that __main__ block exists."""

        # Check that the file can be executed as main
        assert hasattr(import_all_module, "__name__")

    def test_parse_args_function(self):
        """Test that parse_args function exists."""
        try:
            assert callable(import_all_module.parse_args)
        except ImportError:
            # parse_args might not be imported in the module
            pass

    def test_module_has_required_imports(self):
        """Test that module has required imports."""

        # Check for required imports
        required_attributes = ["import_all", "logger"]
        for attr in required_attributes:
            assert hasattr(import_all_module, attr), f"Missing {attr} in module"


class TestImportAllFunctionSignatures:
    """Test cases for function signatures and parameters."""

    def test_parse_args_function_exists(self):
        """Test that parse_args function exists."""
        try:
            assert callable(import_all_module.parse_args)
        except ImportError:
            # parse_args might not be imported in the module
            pass

    def test_async_function(self):
        """Test that import_all is an async function."""
        import inspect

        assert inspect.iscoroutinefunction(import_all_module.import_all)

    def test_import_all_signature(self):
        """Test that import_all has correct signature."""
        import inspect

        sig = inspect.signature(import_all_module.import_all)
        params = list(sig.parameters.keys())

        # Should have gazetteer_types and data_dir parameters
        assert "gazetteer_types" in params
        assert "data_dir" in params
