#!/usr/bin/env python3
import os

import pytest
import yaml

CONFIG_FILE = "export_config.yml"


@pytest.mark.skipif(
    not os.path.exists(CONFIG_FILE),
    reason=f"Test requires {CONFIG_FILE} to exist at project root (optional for development)",
)
def test_yaml_parsing():
    """Test parsing of export_config.yml if it exists."""
    with open(CONFIG_FILE) as f:
        content = f.read()

    config = yaml.safe_load(content)
    assert config is not None, "Config should parse to a non-None object"

    export_list = config.get("export", [])
    assert isinstance(export_list, list), "export key should be a list"
    assert len(export_list) > 0, "export list should not be empty"

    # Validate first export item
    first_export = export_list[0]
    assert "name" in first_export, "Each export item should have a 'name'"
    assert "source" in first_export, "Each export item should have a 'source'"
