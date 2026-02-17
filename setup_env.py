from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent
SYSTEM_DIR = BASE_DIR / "system"
STATE_FILE = SYSTEM_DIR / "setup_state.json"
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"


def run_cmd(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, text=True)


def pip_install(args: list[str]) -> None:
    run_cmd([sys.executable, "-m", "pip", *args])


def read_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_state(state: Dict[str, Any]) -> None:
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def requirements_hash() -> str:
    return hashlib.sha256(REQUIREMENTS_FILE.read_bytes()).hexdigest()


def running_in_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def should_skip_setup(state: Dict[str, Any], req_hash: str, force: bool) -> bool:
    if force:
        return False
    if state.get("requirements_hash") != req_hash:
        return False
    if state.get("python_executable") != sys.executable:
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Python environment for MP4 Downloader.")
    parser.add_argument("--force", action="store_true", help="Force reinstall even if setup state matches.")
    parser.add_argument("--skip-pip-upgrade", action="store_true", help="Skip pip self-upgrade.")
    return parser.parse_args()


def check_external_tools() -> None:
    ffmpeg_found = shutil.which("ffmpeg") is not None
    if not ffmpeg_found:
        print("Warning: ffmpeg not found in PATH. Merging/conversion to MP4 may fail.")


def main() -> int:
    args = parse_args()

    if not REQUIREMENTS_FILE.exists():
        print(f"Error: requirements file not found: {REQUIREMENTS_FILE}")
        return 1

    if not running_in_venv():
        print("Warning: no virtual environment detected. Continuing anyway.")

    req_hash = requirements_hash()
    state = read_state()

    if should_skip_setup(state, req_hash, force=args.force):
        print("Environment already prepared. Skipping dependency install.")
        check_external_tools()
        return 0

    try:
        if not args.skip_pip_upgrade:
            print("Upgrading pip...")
            pip_install(["install", "--upgrade", "pip"])

        print("Installing project requirements...")
        pip_install(["install", "-r", str(REQUIREMENTS_FILE)])
    except subprocess.CalledProcessError as exc:
        print(f"Dependency installation failed. Command: {' '.join(exc.cmd)}")
        return exc.returncode or 1

    write_state(
        {
            "python_executable": sys.executable,
            "requirements_hash": req_hash,
        }
    )

    print("Environment setup complete.")
    check_external_tools()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
