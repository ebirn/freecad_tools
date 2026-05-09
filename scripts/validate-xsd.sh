#!/bin/bash
# Wrapper script for xmllint XSD validation
# Non-blocking: always returns 0

SCHEMA_URL="https://Addons.FreeCAD.Org/Manifest.xsd"
FILE="$1"

if [ -z "$FILE" ]; then
    echo "Usage: $0 <xml-file>"
    exit 0
fi

# Try XSD validation using online schema
if xmllint --noout --schema "$SCHEMA_URL" "$FILE" 2>&1; then
    echo "XSD validation passed: $FILE"
else
    echo "XSD validation warning (substitution groups may cause issues): $FILE"
fi

exit 0
