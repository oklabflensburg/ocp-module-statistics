import ast
import re
from pathlib import Path

PACKAGE = Path(__file__).parents[1] / "src" / "ocp_module_statistics"


def test_host_imports_use_only_public_sdk() -> None:
    host_imports: list[str] = []
    for source in PACKAGE.rglob("*.py"):
        tree = ast.parse(source.read_text(), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
                host_imports.append(node.module)
            if isinstance(node, ast.Import):
                host_imports.extend(
                    alias.name for alias in node.names if alias.name.startswith("app.")
                )
    assert set(host_imports) == {"app.platform.modules.sdk"}


def test_runtime_sql_is_read_only_and_has_no_analysis_area_hierarchy_policy() -> None:
    source = (PACKAGE / "application/query_service.py").read_text().lower()
    assert all(
        table in source
        for table in (
            "external_area_mappings",
            "statistical_datasets",
            "statistical_metrics",
            "statistical_observations",
        )
    )
    assert not re.search(r"\b(insert|update|delete|commit|rollback|flush)\b", source)
    assert "quarter" not in source
    assert "analysis_areas" not in source


def test_module_does_not_ship_or_claim_migrations() -> None:
    assert not (PACKAGE / "migrations").exists()
    assert "ModuleMigrationSource" not in (PACKAGE / "module.py").read_text()
