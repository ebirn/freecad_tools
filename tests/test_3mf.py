import sys
import xml.etree.ElementTree as ET
import zipfile


def validate_3mf(filepath):
    """Validate 3MF file structure for common issues"""
    issues = []

    try:
        with zipfile.ZipFile(filepath, "r") as z:
            # Check required files
            required = ["[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"]
            for required_file in required:
                if required_file not in z.namelist():
                    issues.append(f"Missing required file: {required_file}")

            # Validate XML structure
            try:
                ET.fromstring(z.read("[Content_Types].xml"))
                ET.fromstring(z.read("3D/3dmodel.model"))
                ET.fromstring(z.read("_rels/.rels"))
            except ET.ParseError as e:
                issues.append(f"Invalid XML: {e}")

            # Check if STL files are referenced or present
            stl_files = [f for f in z.namelist() if f.endswith(".stl")]
            if not stl_files:
                issues.append("No STL files found in 3D/ directory")
            else:
                print(f"✓ Found {len(stl_files)} STL files:")
                for stl in stl_files:
                    size = z.getinfo(stl).file_size
                    print(f"  - {stl} ({size:,} bytes)")

            # Check model resources
            try:
                model_xml = ET.fromstring(z.read("3D/3dmodel.model"))
                ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
                resources = model_xml.findall(".//m:resources", ns)
                if resources:
                    objects = model_xml.findall(".//m:object", ns)
                    if objects:
                        print(f"✓ Model has {len(objects)} object definitions")
                    else:
                        print("⚠ Model has resources section but no objects")
                else:
                    print("⚠ Model has empty resources section")
            except Exception as e:
                issues.append(f"Error parsing model XML: {e}")

            # Check relationships
            try:
                rels_xml = ET.fromstring(z.read("_rels/.rels"))
                ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
                rels_list = rels_xml.findall(".//r:Relationship", ns)
                print(f"✓ Relationships defined: {len(rels_list)}")
                for rel in rels_list:
                    print(f"  - {rel.get('Id')}: {rel.get('Target')}")
            except Exception as e:
                issues.append(f"Error parsing relationships: {e}")

    except zipfile.BadZipFile:
        issues.append("File is not a valid ZIP archive")
    except Exception as e:
        issues.append(f"Unexpected error: {e}")

    return issues


if __name__ == "__main__":
    print("=" * 70)
    print("3MF VALIDATION")
    print("=" * 70)
    filepath = "prints/Moxon_OE1EBG.3mf"
    issues = validate_3mf(filepath)

    if issues:
        print("\n⚠ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("\n✓ 3MF file structure is valid!")
        sys.exit(0)
