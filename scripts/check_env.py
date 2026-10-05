"""Environment check for LineageRCA.

Run from the execution folder:  python scripts/check_env.py

Read-only for the project: it installs and changes nothing. It writes only a tiny throw-away Delta table into the
system temp folder for the time-travel smoke test. Prints [OK] / [WARN] / [FAIL] per check.
Exit code 1 if any REQUIRED check fails, otherwise 0.
WARN items are optional or recommended (Java/Docker are only needed for stretch work).
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PACKAGES = {  # import name -> distribution name
    "numpy": "numpy",
    "pandas": "pandas",
    "pyarrow": "pyarrow",
    "deltalake": "deltalake",
    "duckdb": "duckdb",
    "pydantic": "pydantic",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "matplotlib": "matplotlib",
    "jinja2": "jinja2",
    "rich": "rich",
}
DEV_PACKAGES = {"pytest": "pytest", "pytest_cov": "pytest-cov"}
OPTIONAL_PACKAGES = {"pyiceberg": "pyiceberg", "openlineage": "openlineage-python"}
OPTIONAL_TOOLS = {
    "docker": ["docker", "--version"],
    "java": ["java", "-version"],
}
REQUIRED_DIRS = [
    "adapters", "agents", "configs", "core", "demo", "docs", "drift", "logs", "metrics",
    "outputs", "results", "run_logging", "runners", "scripts", "tasks", "tests",
]
REQUIRED_FILES = [
    "CLAUDE.md", "ARCHITECTURE.md", "PROGRESS.md", "build_logs.md", "README.md",
    ".env", ".env.example", ".gitignore", "pytest.ini", "requirements.txt", "requirements-dev.txt",
]

results: list[tuple[str, str, str]] = []  # (level, name, detail)


def add(level: str, name: str, detail: str = "") -> None:
    results.append((level, name, detail))


def run(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    """Run a read-only command; return (exit code, first line of output)."""
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
        text = (proc.stdout or proc.stderr or "").strip().splitlines()
        return proc.returncode, (text[0] if text else "")
    except FileNotFoundError:
        return 127, "not found"
    except Exception as exc:  # noqa: BLE001 - report any problem, never crash the check
        return 1, f"{type(exc).__name__}: {exc}"


def check_python() -> None:
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) < (3, 10):
        add("FAIL", "Python >= 3.10", f"found {ver} at {sys.executable}")
    elif (v.major, v.minor) == (3, 12):
        add("OK", "Python 3.12", f"{ver} at {sys.executable}")
    else:
        add("WARN", "Python 3.12 preferred", f"found {ver} (works, but the team targets 3.12)")
    in_venv = sys.prefix != sys.base_prefix
    if in_venv and ".venv312" in sys.prefix.replace("\\", "/"):
        add("OK", "Virtual env .venv312 active", sys.prefix)
    elif in_venv:
        add("WARN", "A venv is active but it is not .venv312", sys.prefix)
    else:
        add("FAIL", "Virtual env active", "not in a venv; create .venv312 and activate it (see README.md)")


def check_packages() -> None:
    for group, level, packages in (
        ("required", "FAIL", REQUIRED_PACKAGES),
        ("dev", "WARN", DEV_PACKAGES),
        ("optional/stretch", "WARN", OPTIONAL_PACKAGES),
    ):
        for module, dist in packages.items():
            try:
                importlib.import_module(module)
                try:
                    version = metadata.version(dist)
                except metadata.PackageNotFoundError:
                    version = "?"
                add("OK", f"package {dist} ({group})", version)
            except Exception as exc:  # noqa: BLE001
                add(level, f"package {dist} ({group})", f"missing: pip install -r requirements*.txt ({type(exc).__name__})")
    ruff = shutil.which("ruff")
    add("OK" if ruff else "WARN", "ruff (dev tool)", ruff or "missing: pip install -r requirements-dev.txt")


def check_time_travel() -> None:
    """Smoke test of the core mechanism: write two Delta versions, read version 0 back, query it with DuckDB."""
    try:
        import duckdb
        import pyarrow as pa
        from deltalake import DeltaTable, write_deltalake
    except Exception as exc:  # noqa: BLE001
        add("FAIL", "Delta time-travel smoke test", f"cannot import deltalake/duckdb/pyarrow ({type(exc).__name__})")
        return
    try:
        with tempfile.TemporaryDirectory(prefix="lineagerca_smoke_") as tmp:
            path = str(Path(tmp) / "t")
            write_deltalake(path, pa.table({"k": [1, 2, 3], "v": [10.0, 20.0, 30.0]}))
            write_deltalake(path, pa.table({"k": [1, 2, 3, 4], "v": [10.0, 20.0, 30.0, 40.0]}), mode="overwrite")
            old = DeltaTable(path, version=0).to_pyarrow_table()
            now = DeltaTable(path).to_pyarrow_table()
            total = duckdb.sql("select sum(v) from old").fetchone()[0]
            ok = old.num_rows == 3 and now.num_rows == 4 and float(total) == 60.0
            add("OK" if ok else "FAIL", "Delta time-travel smoke test",
                f"version 0 has {old.num_rows} rows, latest has {now.num_rows}, DuckDB sum on old = {total}")
    except Exception as exc:  # noqa: BLE001
        add("FAIL", "Delta time-travel smoke test", f"{type(exc).__name__}: {exc}")


def check_warehouse_dir() -> None:
    raw = os.environ.get("WAREHOUSE_DIR", "")
    env = ROOT / ".env"
    if not raw and env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("WAREHOUSE_DIR="):
                raw = line.split("=", 1)[1].strip()
    if not raw:
        add("WARN", "WAREHOUSE_DIR", "not set in .env; the default %USERPROFILE%\\lineagerca_warehouse will be used")
        return
    path = Path(os.path.expandvars(raw))
    problems = []
    if not path.name.endswith("lineagerca_warehouse"):
        problems.append("folder name must end with 'lineagerca_warehouse' (safety rule)")
    if "onedrive" in str(path).lower():
        problems.append("path is inside OneDrive; sync can lock Delta files")
    add("OK" if not problems else "WARN", "WAREHOUSE_DIR", str(path) if not problems else f"{path}: " + "; ".join(problems))


def check_layout() -> None:
    missing_dirs = [d for d in REQUIRED_DIRS if not (ROOT / d).is_dir()]
    missing_files = [f for f in REQUIRED_FILES if not (ROOT / f).is_file()]
    add("OK" if not missing_dirs else "FAIL", "folder layout", "all 16 folders present" if not missing_dirs else f"missing: {missing_dirs}")
    add("OK" if not missing_files else "FAIL", "guidance/config files", "all present" if not missing_files else f"missing: {missing_files}")
    env, example = ROOT / ".env", ROOT / ".env.example"
    if env.is_file() and example.is_file():
        def keys(path: Path) -> set[str]:
            out = set()
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    out.add(line.split("=", 1)[0].strip())
            return out
        absent = sorted(keys(example) - keys(env))
        add("OK" if not absent else "WARN", ".env has every key of .env.example", "yes" if not absent else f"missing keys: {absent}")


def check_git() -> None:
    code, line = run(["git", "--version"])
    if code != 0:
        add("WARN", "git installed", "git not found (you need it to commit; Claude Code never commits)")
        return
    add("OK", "git installed", line)
    code, _ = run(["git", "rev-parse", "--is-inside-work-tree"])
    if code != 0:
        add("WARN", "git repository", "not a repo yet (the team creates it; Claude Code prints the commands)")
        return
    add("OK", "git repository", "inside a work tree")
    for path in (".env", ".venv312"):
        ignored, _ = run(["git", "check-ignore", "-q", path])
        add("OK" if ignored == 0 else "FAIL", f"{path} is git-ignored", "yes" if ignored == 0 else "NOT ignored: fix .gitignore before any commit")


def check_tools() -> None:
    for name, cmd in OPTIONAL_TOOLS.items():
        if shutil.which(cmd[0]) is None:
            add("WARN", f"{name} (optional, stretch only)", "not installed; the demo does not need it; do NOT install without asking the user")
            continue
        code, line = run(cmd, timeout=15)
        add("OK" if code == 0 else "WARN", f"{name} (optional, stretch only)", line or f"exit {code}")


def main() -> int:
    check_python()
    check_packages()
    check_time_travel()
    check_warehouse_dir()
    check_layout()
    check_git()
    check_tools()
    width = max(len(name) for _, name, _ in results)
    for level, name, detail in results:
        print(f"[{level:<4}] {name:<{width}}  {detail}")
    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print()
    print(f"Summary: {len(results) - len(fails) - len(warns)} OK, {len(warns)} WARN, {len(fails)} FAIL")
    if fails:
        print("NOT READY: fix the FAIL items above (required).")
        return 1
    print("READY for the LineageRCA demo build (WARN items are optional or recommended).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
