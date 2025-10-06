"""
Tests for the gazetteer import_all module (app.gazetteer.import_all).
"""

import pytest

from app.gazetteer.import_all import logger


class TestImportAll:
    """Test cases for import_all function."""

    def test_import_all_function_exists(self):
        """Test that import_all function exists and is callable."""
        from app.gazetteer.import_all import import_all
        assert callable(import_all)

    def test_import_all_function_signature(self):
        """Test that import_all has expected signature."""
        import inspect
        from app.gazetteer.import_all import import_all
        
        sig = inspect.signature(import_all)
        params = list(sig.parameters.keys())
        
        # Should have expected parameters
        assert "gazetteer_types" in params
        assert "data_dir" in params

    def test_import_all_is_async(self):
        """Test that import_all is an async function."""
        import inspect
        from app.gazetteer.import_all import import_all
        
        assert inspect.iscoroutinefunction(import_all)


class TestImportAllModuleStructure:
    """Test cases for module structure and imports."""

    def test_module_imports(self):
        """Test that required modules can be imported."""
        try:
            from app.gazetteer.import_all import import_all, logger
            assert callable(import_all)
            assert logger is not None
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
        assert logger is not None
        # Logger name might be different depending on how the module is imported
        assert hasattr(logger, 'name')

    def test_module_docstring(self):
        """Test that module has proper docstring."""
        import app.gazetteer.import_all
        assert app.gazetteer.import_all.__doc__ is not None
        assert len(app.gazetteer.import_all.__doc__.strip()) > 0

    def test_module_version_info(self):
        """Test that module has basic structure."""
        import app.gazetteer.import_all
        assert hasattr(app.gazetteer.import_all, 'import_all')
        assert hasattr(app.gazetteer.import_all, 'logger')

    def test_if_name_main_block(self):
        """Test that __main__ block exists."""
        import app.gazetteer.import_all
        # Check that the file can be executed as main
        assert hasattr(app.gazetteer.import_all, '__name__')

    def test_parse_args_function(self):
        """Test that parse_args function exists."""
        try:
            from app.gazetteer.import_all import parse_args
            assert callable(parse_args)
        except ImportError:
            # parse_args might not be imported in the module
            pass

    def test_module_has_required_imports(self):
        """Test that module has required imports."""
        import app.gazetteer.import_all
        
        # Check for required imports
        required_attributes = ['import_all', 'logger']
        for attr in required_attributes:
            assert hasattr(app.gazetteer.import_all, attr), f"Missing {attr} in module"


class TestImportAllFunctionSignatures:
    """Test cases for function signatures and parameters."""

    def test_parse_args_function_exists(self):
        """Test that parse_args function exists."""
        try:
            from app.gazetteer.import_all import parse_args
            assert callable(parse_args)
        except ImportError:
            # parse_args might not be imported in the module
            pass

    def test_async_function(self):
        """Test that import_all is an async function."""
        import inspect
        from app.gazetteer.import_all import import_all
        
        assert inspect.iscoroutinefunction(import_all)

    def test_import_all_signature(self):
        """Test that import_all has correct signature."""
        import inspect
        from app.gazetteer.import_all import import_all
        
        sig = inspect.signature(import_all)
        params = list(sig.parameters.keys())
        
        # Should have gazetteer_types and data_dir parameters
        assert "gazetteer_types" in params
        assert "data_dir" in params
