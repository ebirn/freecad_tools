#!/usr/bin/env python3
"""Tests for BOM CSV generation utilities."""

import csv
import json
import sys
from pathlib import Path

import pytest

# Add tools/ to path
_test_dir = Path(__file__).parent
_tools_dir = _test_dir.parent / "tools"
sys.path.insert(0, str(_tools_dir))

import bom_utils  # noqa: E402


class TestBOMCSVGeneration:
    """Tests for CSV generation from BOM data."""

    def test_write_bom_csv_basic(self, tmp_path):
        """Should write basic BOM data to CSV."""
        # Given
        bom_data = [
            {"label": "Part1", "quantity": 2},
            {"label": "Part2", "quantity": 1},
            {"label": "Part3", "quantity": 3},
        ]
        output_file = tmp_path / "bom.csv"

        # When
        success = bom_utils.write_bom_csv(bom_data, str(output_file))

        # Then
        assert success is True
        assert output_file.exists()

        # Verify CSV content
        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 3
        assert rows[0]["label"] == "Part1"
        assert rows[0]["quantity"] == "2"
        assert rows[1]["label"] == "Part2"
        assert rows[2]["label"] == "Part3"

    def test_write_bom_csv_with_custom_fields(self, tmp_path):
        """Should write BOM with custom fields."""
        # Given
        bom_data = [
            {"label": "Part1", "quantity": 2, "material": "Steel", "url": "http://example.com"},
            {"label": "Part2", "quantity": 1, "material": "Aluminum"},
        ]
        output_file = tmp_path / "bom.csv"
        fields = ["label", "quantity", "material", "url"]

        # When
        success = bom_utils.write_bom_csv(bom_data, str(output_file), fields=fields)

        # Then
        assert success is True

        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["material"] == "Steel"
        assert rows[0]["url"] == "http://example.com"
        assert rows[1]["material"] == "Aluminum"
        assert rows[1]["url"] == ""  # restval empty string

    def test_write_bom_csv_empty_data(self, tmp_path):
        """Should handle empty BOM data gracefully."""
        # Given
        bom_data = []
        output_file = tmp_path / "bom.csv"

        # When
        success = bom_utils.write_bom_csv(bom_data, str(output_file))

        # Then
        assert success is True

    def test_write_bom_csv_field_order(self, tmp_path):
        """Should respect field order in CSV."""
        # Given
        bom_data = [
            {"label": "Part1", "quantity": 2, "material": "Steel", "price": 10.50},
        ]
        output_file = tmp_path / "bom.csv"
        fields = ["label", "material", "price", "quantity"]  # Custom order

        # When
        bom_utils.write_bom_csv(bom_data, str(output_file), fields=fields)

        # Then
        with open(output_file) as f:
            reader = csv.reader(f)
            header = next(reader)

        assert header == ["label", "material", "price", "quantity"]

    def test_write_bom_csv_unicode(self, tmp_path):
        """Should handle Unicode characters in data."""
        # Given
        bom_data = [
            {"label": "Körper", "quantity": 2},
            {"label": "部品", "quantity": 1},
        ]
        output_file = tmp_path / "bom.csv"

        # When
        success = bom_utils.write_bom_csv(bom_data, str(output_file))

        # Then
        assert success is True

        with open(output_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["label"] == "Körper"
        assert rows[1]["label"] == "部品"

    def test_write_bom_csv_with_special_chars(self, tmp_path):
        """Should handle special characters and quotes in CSV."""
        # Given
        bom_data = [
            {"label": 'Part with "quotes"', "quantity": 1},
            {"label": "Part with, commas", "quantity": 2},
        ]
        output_file = tmp_path / "bom.csv"

        # When
        success = bom_utils.write_bom_csv(bom_data, str(output_file))

        # Then
        assert success is True

        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["label"] == 'Part with "quotes"'
        assert rows[1]["label"] == "Part with, commas"


class TestBOMJsonConfig:
    """Tests for reading BOM from JSON config."""

    def test_create_bom_from_json_config(self, tmp_path):
        """Should create BOM CSV from JSON config."""
        # Given
        json_config = {
            "bom_data": [
                {"label": "Part1", "quantity": 2},
                {"label": "Part2", "quantity": 1},
            ],
            "fields": ["label", "quantity"],
        }
        json_file = tmp_path / "bom_config.json"
        json_file.write_text(json.dumps(json_config))
        output_file = tmp_path / "output.csv"

        # When
        success = bom_utils.create_bom_from_json_config(str(json_file), str(output_file))

        # Then
        assert success is True
        assert output_file.exists()

        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["label"] == "Part1"

    def test_create_bom_from_json_config_with_custom_fields(self, tmp_path):
        """Should handle JSON config with custom fields."""
        # Given
        json_config = {
            "bom_data": [
                {"label": "Part1", "quantity": 2, "material": "Steel", "url": "http://example.com"},
            ],
            "fields": ["label", "quantity", "material", "url"],
        }
        json_file = tmp_path / "bom_config.json"
        json_file.write_text(json.dumps(json_config))
        output_file = tmp_path / "output.csv"

        # When
        success = bom_utils.create_bom_from_json_config(str(json_file), str(output_file))

        # Then
        assert success is True

        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["material"] == "Steel"
        assert rows[0]["url"] == "http://example.com"

    def test_create_bom_from_json_config_missing_file(self, tmp_path):
        """Should handle missing JSON config file."""
        # Given
        json_file = tmp_path / "nonexistent.json"
        output_file = tmp_path / "output.csv"

        # When
        success = bom_utils.create_bom_from_json_config(str(json_file), str(output_file))

        # Then
        assert success is False


class TestBOMEdgeCases:
    """Tests for edge cases in BOM generation."""

    def test_write_bom_csv_field_inference(self, tmp_path):
        """Should infer fields from BOM data when not specified."""
        # Given
        bom_data = [
            {"label": "Part1", "quantity": 2, "material": "Steel"},
            {"label": "Part2", "quantity": 1, "material": "Aluminum", "price": 10.0},
        ]
        output_file = tmp_path / "bom.csv"

        # When
        success = bom_utils.write_bom_csv(bom_data, str(output_file), fields=None)

        # Then
        assert success is True

        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have all unique fields
        assert len(rows) == 2
        assert rows[1].get("price") in ["10.0", ""]

    def test_write_bom_csv_missing_fields(self, tmp_path):
        """Should fill missing fields with empty strings."""
        # Given
        bom_data = [
            {"label": "Part1", "quantity": 2, "material": "Steel"},
            {"label": "Part2", "quantity": 1},  # Missing material
        ]
        output_file = tmp_path / "bom.csv"
        fields = ["label", "quantity", "material"]

        # When
        success = bom_utils.write_bom_csv(bom_data, str(output_file), fields=fields)

        # Then
        assert success is True

        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["material"] == "Steel"
        assert rows[1]["material"] == ""

    def test_write_bom_csv_large_quantity(self, tmp_path):
        """Should handle large quantity values."""
        # Given
        bom_data = [
            {"label": "Part1", "quantity": 10000},
            {"label": "Part2", "quantity": 1},
        ]
        output_file = tmp_path / "bom.csv"

        # When
        success = bom_utils.write_bom_csv(bom_data, str(output_file))

        # Then
        assert success is True

        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["quantity"] == "10000"

    def test_write_bom_csv_numeric_values(self, tmp_path):
        """Should convert numeric values to strings in CSV."""
        # Given
        bom_data = [
            {"label": "Part1", "quantity": 2, "price": 10.50, "weight": 2.5},
        ]
        output_file = tmp_path / "bom.csv"

        # When
        success = bom_utils.write_bom_csv(bom_data, str(output_file))

        # Then
        assert success is True

        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # All values should be strings in CSV
        assert isinstance(rows[0]["quantity"], str)
        assert isinstance(rows[0]["price"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
