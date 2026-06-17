#!/usr/bin/env python3
"""
Export OpenAPI specification to JSON and YAML files.

Usage:
    python scripts/export_openapi.py

Output:
    - openapi.json (JSON format)
    - openapi.yaml (YAML format)
"""

import json
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("Warning: PyYAML not installed. Only JSON will be exported.")
    print("Install with: pip install pyyaml")

from server.main import app  # noqa: E402


def export_openapi():
    """Export OpenAPI spec to files."""
    spec = app.openapi()

    # Export JSON
    json_path = os.path.join(PROJECT_ROOT, "openapi.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
    print(f"✓ Exported OpenAPI JSON: {json_path}")
    print(f"  Size: {os.path.getsize(json_path) / 1024:.1f} KB")

    # Export YAML if available
    if YAML_AVAILABLE:
        yaml_path = os.path.join(PROJECT_ROOT, "openapi.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(spec, f, allow_unicode=True, default_flow_style=False)
        print(f"✓ Exported OpenAPI YAML: {yaml_path}")
        print(f"  Size: {os.path.getsize(yaml_path) / 1024:.1f} KB")

    # Print summary
    print("\nOpenAPI Specification Summary:")
    print(f"  Title: {spec['info']['title']}")
    print(f"  Version: {spec['info']['version']}")
    print(f"  Endpoints: {len(spec['paths'])}")
    print(f"  Components: {len(spec.get('components', {}).get('schemas', {}))}")

    # List endpoints
    print("\nAvailable Endpoints:")
    for path, methods in sorted(spec["paths"].items()):
        for method in methods.keys():
            print(f"  {method.upper():6s} {path}")


if __name__ == "__main__":
    export_openapi()
