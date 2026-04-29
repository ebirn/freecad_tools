#!/usr/bin/env python3
"""Tests for body_screenshot module and screenshot configuration."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add tools/ to path for importing
_test_dir = Path(__file__).parent
_tools_dir = _test_dir.parent / "tools"
sys.path.insert(0, str(_tools_dir))


class TestScreenshotConfigDefaults:
    """Tests for screenshot configuration defaults and merging."""

    def test_default_screenshot_config_values(self):
        """Default screenshot config should have expected values."""
        # Given/When - import from body_screenshot when it exists
        # This test will fail until body_screenshot.py is created with DEFAULT_CONFIG
        from body_screenshot import DEFAULT_SCREENSHOT_CONFIG

        # Then
        assert DEFAULT_SCREENSHOT_CONFIG["enabled"] is False
        assert DEFAULT_SCREENSHOT_CONFIG["output_dir"] == "prints/images/"
        assert DEFAULT_SCREENSHOT_CONFIG["views"] == ["isometric"]
        assert DEFAULT_SCREENSHOT_CONFIG["resolution"] == [1920, 1080]
        assert DEFAULT_SCREENSHOT_CONFIG["background"] == [255, 255, 255, 255]
        assert DEFAULT_SCREENSHOT_CONFIG["format"] == "png"
        assert DEFAULT_SCREENSHOT_CONFIG["composite"] is True

    def test_get_screenshot_config_with_bool_enabled(self):
        """Screenshot config from boolean true should merge with defaults."""
        from body_screenshot import get_screenshot_config

        # Given
        export_item = {"screenshots": True}

        # When
        result = get_screenshot_config(export_item)

        # Then
        assert result["enabled"] is True
        assert result["views"] == ["isometric"]  # default
        assert result["format"] == "png"  # default

    def test_get_screenshot_config_with_full_dict(self):
        """Full screenshot config dict should override defaults."""
        from body_screenshot import get_screenshot_config

        # Given
        export_item = {
            "screenshots": {
                "enabled": True,
                "views": ["front", "top"],
                "resolution": [1024, 768],
                "format": "jpg",
            }
        }

        # When
        result = get_screenshot_config(export_item)

        # Then
        assert result["enabled"] is True
        assert result["views"] == ["front", "top"]
        assert result["resolution"] == [1024, 768]
        assert result["format"] == "jpg"
        # Defaults should still apply for unspecified fields
        assert result["output_dir"] == "prints/images/"
        assert result["background"] == [255, 255, 255, 255]

    def test_get_screenshot_config_with_partial_dict(self):
        """Partial screenshot config should merge with defaults."""
        from body_screenshot import get_screenshot_config

        # Given
        export_item = {"screenshots": {"format": "jpg"}}

        # When
        result = get_screenshot_config(export_item)

        # Then
        assert result["format"] == "jpg"
        assert result["enabled"] is False  # default
        assert result["views"] == ["isometric"]  # default

    def test_get_screenshot_config_with_no_screenshots_key(self):
        """Missing screenshots key should return defaults with enabled=False."""
        from body_screenshot import get_screenshot_config

        # Given
        export_item = {}

        # When
        result = get_screenshot_config(export_item)

        # Then
        assert result["enabled"] is False
        assert result["views"] == ["isometric"]
        assert result["format"] == "png"


class TestScreenshotConfigValidation:
    """Tests for validating screenshot configuration values."""

    def test_validate_views_list(self):
        """Valid view names should be accepted."""
        from body_screenshot import validate_screenshot_config

        config = {"views": ["isometric", "front", "top"]}
        # Should not raise
        validate_screenshot_config(config)

    def test_validate_invalid_view_raises(self):
        """Invalid view names should raise ValueError."""
        from body_screenshot import validate_screenshot_config

        config = {"views": ["isometric", "invalid_view"]}

        with pytest.raises(ValueError, match="Invalid view"):
            validate_screenshot_config(config)

    def test_validate_resolution_list_of_two(self):
        """Resolution must be list of exactly 2 positive integers."""
        from body_screenshot import validate_screenshot_config

        # Valid
        config = {"resolution": [1920, 1080]}
        validate_screenshot_config(config)

        # Invalid - not 2 elements
        config = {"resolution": [1920]}
        with pytest.raises(ValueError, match="Resolution must be"):
            validate_screenshot_config(config)

    def test_validate_background_rgba(self):
        """Background must be RGBA list of 4 values 0-255."""
        from body_screenshot import validate_screenshot_config

        # Valid
        config = {"background": [255, 255, 255, 255]}
        validate_screenshot_config(config)

        # Invalid - wrong length
        config = {"background": [255, 255, 255]}
        with pytest.raises(ValueError, match="Background must be RGBA"):
            validate_screenshot_config(config)

    def test_validate_format_png_or_jpg(self):
        """Format must be png or jpg."""
        from body_screenshot import validate_screenshot_config

        # Valid
        config = {"format": "png"}
        validate_screenshot_config(config)
        config = {"format": "jpg"}
        validate_screenshot_config(config)

        # Invalid
        config = {"format": "gif"}
        with pytest.raises(ValueError, match="Format must be"):
            validate_screenshot_config(config)


class TestBuildScreenshotConfig:
    """Tests for building screenshot config from export item."""

    def test_build_screenshot_config_from_export_item(self):
        """Build full config from export item with screenshots."""
        from body_screenshot import build_screenshot_config

        # Given
        export_item = {
            "name": "MyProject",
            "bodies": ["Body1", "Body2"],
            "source": "/path/to/project.FCStd",
        }
        screenshot_cfg = {
            "enabled": True,
            "output_dir": "docs/images/",
            "views": ["isometric", "front"],
        }

        result = build_screenshot_config(export_item, screenshot_cfg)

        assert result["source"] == "/path/to/project.FCStd"
        assert result["bodies"] == ["Body1", "Body2"]
        assert result["views"] == ["isometric", "front"]
        assert "output_dir" in result

    def test_build_screenshot_config_with_absolute_paths(self):
        """Output dir should be resolved to absolute path."""
        from body_screenshot import build_screenshot_config

        export_item = {
            "name": "MyProject",
            "bodies": ["Body1"],
            "source": "/path/to/project.FCStd",
        }
        screenshot_cfg = {
            "enabled": True,
            "output_dir": "docs-images/",
        }

        with patch("os.path.abspath") as mock_abspath:
            mock_abspath.return_value = "/absolute/docs-images"
            result = build_screenshot_config(export_item, screenshot_cfg)

        assert result["output_dir"] == "/absolute/docs-images"


class TestViewOrientations:
    """Tests for view orientation mapping."""

    def test_view_orientations_dict_exists(self):
        """VIEW_ORIENTATIONS should map all supported view names."""
        from body_screenshot import VIEW_ORIENTATIONS

        expected_views = ["isometric", "front", "top", "right", "back", "bottom", "left"]
        for view in expected_views:
            assert view in VIEW_ORIENTATIONS, f"Missing view: {view}"

    def test_view_orientation_is_string_method_name(self):
        """Each view orientation should be a string method name."""
        from body_screenshot import VIEW_ORIENTATIONS

        for view_name, method_name in VIEW_ORIENTATIONS.items():
            assert isinstance(method_name, str), f"{view_name} should be string, got {type(method_name)}"
            assert method_name.startswith("view"), f"{view_name} method name should start with 'view'"
