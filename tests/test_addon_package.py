"""
Tests for FreeCAD Addon Manager package.xml validation.

Validates that the package.xml file is correctly structured for
Addon Manager distribution as a macro collection.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# Try to import lxml for XSD validation
try:
    from lxml import etree

    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False


def get_namespace(root):
    """Extract namespace from XML root element."""
    if "{" in root.tag:
        # Tag format is {namespace}localname
        return root.tag.split("{")[1].split("}")[0]
    return ""


def make_ns_map(ns):
    """Create namespace map for ElementTree find operations."""
    return {"manifest": ns} if ns else {}


class TestAddonPackageXml:
    """Test suite for package.xml validation."""

    @pytest.fixture
    def package_xml_path(self):
        """Return path to package.xml file."""
        return Path(__file__).parent.parent / "package.xml"

    @pytest.fixture
    def parsed_package(self, package_xml_path):
        """Parse and return (root, ns_map) of package.xml."""
        if not package_xml_path.exists():
            pytest.skip("package.xml not found")
        tree = ET.parse(package_xml_path)
        root = tree.getroot()
        ns = get_namespace(root)
        ns_map = make_ns_map(ns)
        return root, ns_map

    def test_package_xml_exists(self, package_xml_path):
        """Test that package.xml exists in project root."""
        assert package_xml_path.exists(), "package.xml not found in project root"

    def test_package_xml_is_valid_xml(self, package_xml_path):
        """Test that package.xml is well-formed XML."""
        try:
            ET.parse(package_xml_path)
        except ET.ParseError as e:
            pytest.fail(f"Invalid XML: {e}")

    @pytest.mark.skipif(not LXML_AVAILABLE, reason="lxml not available")
    def test_package_xml_validates_against_xsd(self, package_xml_path):
        """Test that package.xml validates against the official XSD schema."""
        try:
            # Parse package.xml
            xml_doc = etree.parse(str(package_xml_path))

            # Extract schema location from package.xml
            root = xml_doc.getroot()
            schema_loc = root.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")

            if not schema_loc:
                pytest.skip("No schemaLocation found in package.xml")

            # schemaLocation format: "namespace schema_url"
            parts = schema_loc.split()
            if len(parts) < 2:
                pytest.skip("Invalid schemaLocation format")

            schema_url = parts[1]

            # Cache schema in test_output/ (not in repo)
            cache_dir = Path(__file__).parent.parent / "test_output" / "Addon-Schema"
            cache_dir.mkdir(parents=True, exist_ok=True)
            xsd_path = cache_dir / "Manifest.xsd"

            # Download schema if not cached
            if not xsd_path.exists():
                import urllib.request

                try:
                    with urllib.request.urlopen(schema_url, timeout=10) as response:
                        xsd_content = response.read()
                        xsd_path.write_bytes(xsd_content)
                except Exception as e:
                    pytest.skip(f"Could not download XSD schema: {e}")

            # Load and validate against cached schema
            if xsd_path.exists():
                schema_doc = etree.parse(str(xsd_path))
                schema = etree.XMLSchema(schema_doc)

                if not schema.validate(xml_doc):
                    errors = schema.error_log
                    error_msgs = [f"Line {e.line}: {e.message}" for e in errors]
                    pytest.fail("XSD validation failed:\n" + "\n".join(error_msgs))
            else:
                pytest.skip(f"Could not load XSD schema from {schema_url}")

        except ImportError:
            pytest.skip("lxml not available")
        except Exception as e:
            pytest.skip(f"XSD validation error: {e}")

    def test_package_has_name(self, parsed_package):
        """Test that package has a name element."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        name = root.find(f"{{{ns}}}name") if ns else root.find("name")
        assert name is not None, "Missing <name> element"
        assert name.text and len(name.text) > 0, "Name element is empty"

    def test_package_has_version(self, parsed_package):
        """Test that package has a version element."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        version = root.find(f"{{{ns}}}version") if ns else root.find("version")
        assert version is not None, "Missing <version> element"
        assert version.text and len(version.text) > 0, "Version element is empty"

    def test_package_has_description(self, parsed_package):
        """Test that package has a description element."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        desc = root.find(f"{{{ns}}}description") if ns else root.find("description")
        assert desc is not None, "Missing <description> element"
        assert desc.text and len(desc.text) > 0, "Description element is empty"

    def test_package_has_license(self, parsed_package):
        """Test that package has a license element."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        license_elem = root.find(f"{{{ns}}}license") if ns else root.find("license")
        assert license_elem is not None, "Missing <license> element"
        assert license_elem.text and len(license_elem.text) > 0, "License element is empty"

    def test_package_has_maintainer(self, parsed_package):
        """Test that package has at least one maintainer."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        maintainers = root.findall(f"{{{ns}}}maintainer") if ns else root.findall("maintainer")
        assert len(maintainers) > 0, "Missing <maintainer> element"
        for m in maintainers:
            assert m.text and len(m.text) > 0, "Maintainer name is empty"
            assert "email" in m.attrib, "Maintainer missing email attribute"

    def test_package_has_content_section(self, parsed_package):
        """Test that package has a content section."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        content = root.find(f"{{{ns}}}content") if ns else root.find("content")
        assert content is not None, "Missing <content> element"

    def test_package_has_macro_entries(self, parsed_package):
        """Test that package has macro entries in content section."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        content = root.find(f"{{{ns}}}content") if ns else root.find("content")
        assert content is not None, "Missing <content> element"
        macros = content.findall(f"{{{ns}}}macro") if ns else content.findall("macro")
        assert len(macros) > 0, "No <macro> entries found in <content>"

    def test_macro_entries_have_required_fields(self, parsed_package):
        """Test that each macro entry has required fields."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        content = root.find(f"{{{ns}}}content") if ns else root.find("content")
        assert content is not None
        macros = content.findall(f"{{{ns}}}macro") if ns else content.findall("macro")

        for macro in macros:
            subdir = macro.find(f"{{{ns}}}subdirectory") if ns else macro.find("subdirectory")
            assert subdir is not None, "Macro missing <subdirectory> element"
            assert subdir.text and len(subdir.text) > 0, "Macro subdirectory is empty"

    def test_macro_files_exist(self, parsed_package):
        """Test that referenced macro files actually exist."""
        root, ns_map = parsed_package
        package_dir = Path(__file__).parent.parent
        ns = get_namespace(root)
        content = root.find(f"{{{ns}}}content") if ns else root.find("content")
        assert content is not None
        macros = content.findall(f"{{{ns}}}macro") if ns else content.findall("macro")

        for macro in macros:
            subdir = macro.find(f"{{{ns}}}subdirectory") if ns else macro.find("subdirectory")
            assert subdir is not None, "Macro missing <subdirectory> element"
            subdir_path = package_dir / subdir.text
            assert subdir_path.exists(), f"Macro subdirectory not found: {subdir_path}"
            assert subdir_path.is_dir(), f"Macro subdirectory is not a directory: {subdir_path}"
            macro_files = list(subdir_path.glob("*.py"))
            assert len(macro_files) > 0, f"No macro Python files found in: {subdir_path}"

    def test_package_has_icon(self, parsed_package):
        """Test that package has an icon element."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        icon = root.find(f"{{{ns}}}icon") if ns else root.find("icon")
        assert icon is not None, "Missing <icon> element"
        assert icon.text and len(icon.text) > 0, "Icon element is empty"

    def test_icon_file_exists(self, parsed_package):
        """Test that the icon file exists."""
        root, ns_map = parsed_package
        package_dir = Path(__file__).parent.parent
        ns = get_namespace(root)
        icon = root.find(f"{{{ns}}}icon") if ns else root.find("icon")
        if icon is not None and icon.text:
            icon_path = package_dir / icon.text
            assert icon_path.exists(), f"Icon file not found: {icon_path}"

    def test_package_has_urls(self, parsed_package):
        """Test that package has required URL elements."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        urls = root.findall(f"{{{ns}}}url") if ns else root.findall("url")
        assert len(urls) > 0, "No <url> elements found"

        # Check for repository URL
        repo_urls = [u for u in urls if u.get("type") == "repository"]
        assert len(repo_urls) > 0, "Missing repository URL"

    def test_freecad_version_constraints(self, parsed_package):
        """Test that FreeCAD version constraints are specified."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        freecad_min = root.find(f"{{{ns}}}freecadmin") if ns else root.find("freecadmin")
        # freecadmin is recommended but not strictly required
        if freecad_min is not None:
            assert freecad_min.text and len(freecad_min.text) > 0

    def test_version_matches_pyproject(self, parsed_package, package_xml_path):
        """Test that package.xml version matches pyproject.toml version."""
        import re

        root, ns_map = parsed_package
        ns = get_namespace(root)
        version_elem = root.find(f"{{{ns}}}version") if ns else root.find("version")
        assert version_elem is not None, "Missing <version> element"
        package_version = version_elem.text.strip()

        # Read pyproject.toml
        pyproject_path = package_xml_path.parent / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found"

        content = pyproject_path.read_text()
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        assert match, "Could not find version in pyproject.toml"
        pyproject_version = match.group(1).strip()

        assert package_version == pyproject_version, (
            f"Version mismatch: package.xml={package_version}, pyproject.toml={pyproject_version}"
        )

    def test_license_matches_pyproject(self, parsed_package, package_xml_path):
        """Test that package.xml license matches pyproject.toml license."""
        root, ns_map = parsed_package
        ns = get_namespace(root)
        license_elem = root.find(f"{{{ns}}}license") if ns else root.find("license")
        assert license_elem is not None, "Missing <license> element"
        package_license = license_elem.text.strip()

        # Read pyproject.toml
        pyproject_path = package_xml_path.parent / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found"

        import re

        content = pyproject_path.read_text()
        match = re.search(r'^license\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        assert match, "Could not find license in pyproject.toml"
        pyproject_license = match.group(1).strip()

        assert package_license == pyproject_license, (
            f"License mismatch: package.xml={package_license}, pyproject.toml={pyproject_license}"
        )


class TestMacroMetadata:
    """Test that macro files have proper FreeCAD metadata headers."""

    @pytest.fixture
    def macros_dir(self):
        """Return path to macros directory."""
        return Path(__file__).parent.parent / "macros"

    def test_macro_files_have_metadata(self, macros_dir):
        """Test that macro files have required metadata variables."""
        required_metadata = ["__Name__", "__Comment__", "__Author__", "__Version__", "__License__"]

        macro_files = ["generate_variant_configs.py", "variant_array_assignment.py", "set_export_properties.py"]

        for macro_file in macro_files:
            file_path = macros_dir / macro_file
            if not file_path.exists():
                pytest.skip(f"Macro file not found: {macro_file}")

            content = file_path.read_text()

            for meta in required_metadata:
                assert f"{meta}" in content, f"Macro {macro_file} missing {meta}"

    def test_macro_metadata_values(self, macros_dir):
        """Test that macro metadata has valid values."""
        macro_files = ["generate_variant_configs.py", "variant_array_assignment.py", "set_export_properties.py"]

        for macro_file in macro_files:
            file_path = macros_dir / macro_file
            if not file_path.exists():
                continue

            content = file_path.read_text()

            # Extract __Name__ value
            import re

            name_match = re.search(r'__Name__\s*=\s*["\']([^"\']+)["\']', content)
            assert name_match, f"Macro {macro_file} has invalid __Name__ format"
            assert len(name_match.group(1)) > 0, f"Macro {macro_file} has empty __Name__"

            version_match = re.search(r'__Version__\s*=\s*["\']([^"\']+)["\']', content)
            assert version_match, f"Macro {macro_file} has invalid __Version__ format"
            assert len(version_match.group(1)) > 0, f"Macro {macro_file} has empty __Version__"
