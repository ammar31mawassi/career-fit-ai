from __future__ import annotations

import subprocess
import sys
import time
import uuid
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SUPABASE_ROOT = REPOSITORY_ROOT / "supabase"
TEST_ROOT = SUPABASE_ROOT / "tests"
POSTGRES_IMAGE = "postgres:16-alpine"
UPGRADE_MIGRATIONS = (
    SUPABASE_ROOT
    / "migrations"
    / "20260730170000_tenant_integrity_and_browser_privileges_v19.sql",
    SUPABASE_ROOT
    / "migrations"
    / "20260730190000_job_scan_claims_v20.sql",
    SUPABASE_ROOT
    / "migrations"
    / "20260730210000_backend_mediated_storage_v21.sql",
    SUPABASE_ROOT
    / "migrations"
    / "20260730220000_data_contract_constraints_v22.sql",
)


class HarnessError(RuntimeError):
    pass


def _run(
    arguments: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        arguments,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        command = " ".join(arguments)
        raise HarnessError(
            f"{command} failed with exit code {result.returncode}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result


def _psql(container: str, database: str, sql: str) -> None:
    _run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "--no-psqlrc",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            "postgres",
            "--dbname",
            database,
        ],
        input_text=sql,
    )


def _wait_for_postgres(container: str) -> None:
    deadline = time.monotonic() + 30
    consecutive_ready_checks = 0
    while time.monotonic() < deadline:
        result = _run(
            [
                "docker",
                "exec",
                container,
                "psql",
                "--no-psqlrc",
                "--username",
                "postgres",
                "--dbname",
                "postgres",
                "--command",
                "select 1;",
            ],
            check=False,
        )
        if result.returncode == 0:
            consecutive_ready_checks += 1
            if consecutive_ready_checks >= 3:
                return
        else:
            consecutive_ready_checks = 0
        time.sleep(0.5)
    raise HarnessError("PostgreSQL did not become ready within 30 seconds.")


def _canonical_schema_for_plain_postgres() -> str:
    schema = (SUPABASE_ROOT / "schema.sql").read_text(encoding="utf-8")
    extension_statement = "create extension if not exists pgmq;"
    if schema.lower().count(extension_statement) != 1:
        raise HarnessError(
            "Expected exactly one pgmq extension statement in supabase/schema.sql."
        )
    return schema.replace(
        extension_statement,
        "-- pgmq is supplied by supabase_test_stubs.sql in this harness.",
    )


def _prepare_database(container: str, database: str) -> None:
    _psql(container, "postgres", f'create database "{database}";')
    _psql(
        container,
        database,
        (TEST_ROOT / "supabase_test_stubs.sql").read_text(encoding="utf-8"),
    )
    _psql(container, database, _canonical_schema_for_plain_postgres())


def main() -> int:
    container = f"careerfit-security-{uuid.uuid4().hex[:10]}"
    print(f"Starting isolated {POSTGRES_IMAGE} container {container}...")
    _run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--pull=never",
            "--name",
            container,
            "--env",
            "POSTGRES_PASSWORD=careerfit-test-only",
            POSTGRES_IMAGE,
        ]
    )

    try:
        _wait_for_postgres(container)
        assertions = (TEST_ROOT / "assert_tenant_security.sql").read_text(
            encoding="utf-8"
        )

        print("Checking the fresh-install schema...")
        _prepare_database(container, "careerfit_fresh")
        _psql(container, "careerfit_fresh", assertions)

        for migration in UPGRADE_MIGRATIONS:
            if not migration.exists():
                raise HarnessError(f"Missing migration: {migration}")

        print("Checking the v18-to-v22 upgrade path...")
        _prepare_database(container, "careerfit_upgrade")
        _psql(
            container,
            "careerfit_upgrade",
            (TEST_ROOT / "fixtures" / "v18_security_state.sql").read_text(
                encoding="utf-8"
            ),
        )
        for migration in UPGRADE_MIGRATIONS:
            _psql(
                container,
                "careerfit_upgrade",
                migration.read_text(encoding="utf-8"),
            )
        _psql(container, "careerfit_upgrade", assertions)
    finally:
        _run(["docker", "stop", container], check=False)

    print("Fresh-install and upgrade tenant-security checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HarnessError, OSError) as error:
        print(f"SECURITY HARNESS FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
