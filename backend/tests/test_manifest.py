import json
from pathlib import Path

import yaml


def test_root_manifest_identifies_packages_and_read_only_persistence() -> None:
    root = Path(__file__).parents[2]
    manifest = yaml.safe_load((root / "module.yaml").read_text())
    frontend = json.loads((root / "frontend/module.json").read_text())
    assert manifest["manifest_version"] == 1
    assert manifest["id"] == "statistics"
    assert manifest["version"] == "0.2.0"
    assert manifest["requires"] == {
        "host": ">=0.2.0,<1.0.0",
        "sdk": ">=1.15.0,<2.0.0",
        "modules": {},
    }
    assert manifest["backend"]["package"] == "ocp-module-statistics"
    assert manifest["frontend"]["package"] == "@open-city-planner/statistics"
    assert manifest["capabilities"] == ["statistics.query"]
    assert manifest["persistence"] == {"schema": "statistics", "migrations": False}
    assert frontend["compatibility"]["sdk"] == ">=1.5.0 <2.0.0"
    assert frontend["backendModuleId"] == manifest["id"]
