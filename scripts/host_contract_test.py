from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env={**os.environ, **environment},
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def cli(
    python: Path,
    backend: Path,
    install_root: Path,
    environment: Mapping[str, str],
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return run(
        (str(python), "-m", "app.cli.modules", "--root", str(install_root), *arguments),
        cwd=backend,
        environment=environment,
    )


def json_output(result: subprocess.CompletedProcess[str]) -> dict:
    lines = (line for line in result.stdout.splitlines() if line.startswith("{"))
    return json.loads(next(lines))


def generated_environment(
    python: Path,
    backend: Path,
    install_root: Path,
    environment: Mapping[str, str],
) -> dict[str, str]:
    result = cli(python, backend, install_root, environment, "env", "--format", "json")
    values = json.loads(result.stdout)
    assert set(values) == {
        "ENABLED_MODULES",
        "OCP_BACKEND_MODULES",
        "OCP_ENABLED_INSTALLED_BACKEND_PATHS",
        "OCP_EXCLUDED_BUILTIN_MODULES",
        "OCP_FRONTEND_MODULES",
        "OCP_INSTALLED_FRONTEND_MODULE_ROOTS",
    }
    return values


def frontend_check(frontend: Path, environment: Mapping[str, str]) -> str:
    return run(("pnpm", "modules:check"), cwd=frontend, environment=environment).stdout


def backend_runtime_check(python: Path, backend: Path, environment: Mapping[str, str]) -> None:
    probe = """
from app.core.config import get_settings
from app.main import app, module_runtime
from app.platform.modules import EntryPointModuleDiscovery, FirstPartyModuleDiscovery
from app.platform.modules.runtime import resolve_module_definitions
from app.platform.modules.sdk import (
    STATISTICS_QUERY_SERVICE_ID,
    STATISTICS_QUERY_SERVICE_VERSION,
    StatisticsQueryPort,
)

settings = get_settings()
definitions = resolve_module_definitions(
    enabled_module_ids=settings.enabled_module_list,
    discovery_providers=(FirstPartyModuleDiscovery(), EntryPointModuleDiscovery()),
    host_version=settings.api_version,
)
statistics = [item for item in definitions if item[1].id == "statistics"]
assert len(statistics) == 1
assert statistics[0][0].origin.startswith("entry-point:statistics=")
assert statistics[0][0].persistence is not None
assert statistics[0][0].persistence.migration_source is None
assert statistics[0][0].persistence.adopted_tables == frozenset({
    "external_area_mappings",
    "statistical_datasets",
    "statistical_import_runs",
    "statistical_metrics",
    "statistical_observations",
})
assert statistics[0][0].settings is None
assert statistics[0][1].capabilities == ["statistics.query"]
assert module_runtime.registry.get("statistics").manifest.id == "statistics"
services = module_runtime.registry.get("statistics").context.services
assert services is not None
assert services.require(
    StatisticsQueryPort,
    service_id=STATISTICS_QUERY_SERVICE_ID,
    version=STATISTICS_QUERY_SERVICE_VERSION,
).__class__.__name__ == "SqlStatisticsQueryService"
"""
    run((str(python), "-c", probe), cwd=backend, environment=environment)


def disabled_runtime_check(python: Path, backend: Path, environment: Mapping[str, str]) -> None:
    probe = """
from app.main import app, module_runtime

assert all(item.manifest.id != "statistics" for item in module_runtime.registry.records)
"""
    run((str(python), "-c", probe), cwd=backend, environment=environment)


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    host = Path(sys.argv[1]).resolve()
    bundle = Path(sys.argv[2]).resolve()
    contract = json.loads(
        (repository / ".github/ocp-host-contract.json").read_text(encoding="utf-8")
    )
    actual = run(("git", "rev-parse", "HEAD"), cwd=host, environment={}).stdout.strip()
    if actual != contract["commit"]:
        raise SystemExit(f"Host contract mismatch: expected {contract['commit']}, got {actual}")

    backend = host / "backend"
    frontend = host / "frontend"
    python = backend / ".venv/bin/python"
    with TemporaryDirectory(prefix=".ocp-statistics-contract-", dir=repository) as temporary:
        install_root = Path(temporary) / "modules"
        base_environment = {
            "ENABLED_MODULES": "",
            "OCP_ENABLED_INSTALLED_BACKEND_PATHS": "",
            "OCP_EXCLUDED_BUILTIN_MODULES": "",
            "OCP_FRONTEND_MODULES": "",
            "OCP_INSTALLED_FRONTEND_MODULE_ROOTS": "",
            "OCP_MODULE_INSTALL_ROOT": str(install_root),
        }

        sdk_version = run(
            (
                str(python),
                "-c",
                "from app.platform.modules.runtime import MODULE_SDK_VERSION; print(MODULE_SDK_VERSION)",
            ),
            cwd=backend,
            environment=base_environment,
        ).stdout.strip()
        assert sdk_version == contract["sdk_version"]
        host_version = run(
            (
                str(python),
                "-c",
                "from app.core.config import get_settings; print(get_settings().api_version)",
            ),
            cwd=backend,
            environment=base_environment,
        ).stdout.strip()
        assert host_version == contract["host_version"]
        frontend_contract = (host / "frontend/module-host/contract.ts").read_text(
            encoding="utf-8"
        )
        frontend_sdk = re.search(
            r"FRONTEND_MODULE_SDK_VERSION = '([^']+)'", frontend_contract
        )
        frontend_host = re.search(r"FRONTEND_HOST_VERSION = '([^']+)'", frontend_contract)
        assert frontend_sdk and frontend_sdk.group(1) == contract["frontend_sdk_version"]
        assert frontend_host and frontend_host.group(1) == contract["frontend_host_version"]

        verified = json_output(
            cli(python, backend, install_root, base_environment, "verify", str(bundle))
        )
        installed = json_output(
            cli(python, backend, install_root, base_environment, "install", str(bundle))
        )
        assert installed["id"] == "statistics"
        assert installed["enabled"] is False

        inventory = json_output(
            cli(python, backend, install_root, base_environment, "list", "--format", "json")
        )
        search_inventory = [item for item in inventory["modules"] if item["id"] == "statistics"]
        assert len(search_inventory) == 1
        assert search_inventory[0]["kind"] == "installed"
        assert search_inventory[0]["enabled"] is False

        installed_package = (
            install_root
            / "installed/statistics/0.2.0/backend/site-packages/ocp_module_statistics"
        )
        run(
            (
                str(python),
                str(host / "scripts/check_external_module_imports.py"),
                str(installed_package),
            ),
            cwd=backend,
            environment=base_environment,
        )

        disabled = generated_environment(python, backend, install_root, base_environment)
        assert disabled["OCP_ENABLED_INSTALLED_BACKEND_PATHS"] == ""
        assert disabled["OCP_FRONTEND_MODULES"] == ""
        assert disabled["OCP_INSTALLED_FRONTEND_MODULE_ROOTS"]
        assert "no optional modules enabled" in frontend_check(
            frontend, {**base_environment, **disabled}
        )
        disabled_runtime_check(python, backend, {**base_environment, **disabled})

        cli(python, backend, install_root, base_environment, "enable", "statistics")
        enabled_environment = generated_environment(python, backend, install_root, base_environment)
        assert enabled_environment["ENABLED_MODULES"] == "statistics"
        assert enabled_environment["OCP_BACKEND_MODULES"] == "statistics"
        assert enabled_environment["OCP_FRONTEND_MODULES"] == "statistics"
        assert "site-packages" in enabled_environment["OCP_ENABLED_INSTALLED_BACKEND_PATHS"]
        enabled = {**base_environment, **enabled_environment}
        backend_runtime_check(python, backend, enabled)
        assert "statistics" in frontend_check(frontend, enabled)
        frontend_root = Path(enabled_environment["OCP_INSTALLED_FRONTEND_MODULE_ROOTS"])
        assert (frontend_root / "statistics/module.json").is_file()
        assert (frontend_root / "statistics/layer/nuxt.config.ts").is_file()
        run(("pnpm", "typecheck"), cwd=frontend, environment=enabled)
        run(("pnpm", "build"), cwd=frontend, environment=enabled)

        cli(python, backend, install_root, base_environment, "disable", "statistics")
        after_disable = generated_environment(python, backend, install_root, base_environment)
        assert after_disable == disabled
        assert "no optional modules enabled" in frontend_check(
            frontend, {**base_environment, **after_disable}
        )
        disabled_runtime_check(python, backend, {**base_environment, **after_disable})

        cli(python, backend, install_root, base_environment, "enable", "statistics")
        reenabled = generated_environment(python, backend, install_root, base_environment)
        assert reenabled == enabled_environment
        backend_runtime_check(python, backend, {**base_environment, **reenabled})
        assert "statistics" in frontend_check(frontend, {**base_environment, **reenabled})

        print(
            "host contract passed: bundle verify; install disabled; inventory disabled; "
            "Host import guard; enable; backend entry-point/service discovery; "
            "frontend discovery/typecheck/build; disable without registration; re-enable; "
            f"sha256={verified['bundle_sha256']}"
        )


if __name__ == "__main__":
    main()
