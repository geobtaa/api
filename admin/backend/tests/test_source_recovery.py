"""Old Source writers must stop before opening a client or changing data."""

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("name", ["link_resource_sources", "recover_resource_sources"])
def test_retired_source_writers_explain_set_ownership(name, capsys):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parents[2] / f"scripts/{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 2
    assert "Use link_resource_sets.py" in capsys.readouterr().err
