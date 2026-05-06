from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


APP_NAME = "cc-deepseek-proxy"
ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
RELEASE_DIR = ROOT / "release"
SPEC_FILE = ROOT / f"{APP_NAME}.spec"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build portable Windows package")
    parser.add_argument(
        "--mode",
        choices=("onedir", "onefile"),
        default="onedir",
        help="onedir starts faster; onefile produces a single exe",
    )
    parser.add_argument("--console", action="store_true", help="show a console window for troubleshooting")
    parser.add_argument(
        "--install-missing",
        action="store_true",
        help="install PyInstaller automatically when it is missing",
    )
    parser.add_argument("--skip-clean", action="store_true", help="keep existing build/dist/release folders")
    return parser.parse_args()


def ensure_inside_project(path: Path) -> Path:
    """Protect cleanup from accidentally deleting outside the project."""
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved == root or root not in resolved.parents:
        raise RuntimeError(f"Refusing to remove unsafe path: {resolved}")
    return resolved


def safe_rmtree(path: Path) -> None:
    resolved = ensure_inside_project(path)
    if resolved.exists():
        shutil.rmtree(resolved)


def ensure_pyinstaller(install_missing: bool) -> None:
    try:
        import PyInstaller.__main__  # noqa: F401
        return
    except ModuleNotFoundError:
        if not install_missing:
            raise SystemExit(
                "PyInstaller is not installed. Run:\n"
                "  python -m pip install -r requirements.txt\n"
                "or rerun this script with --install-missing."
            )

    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0,<7"])


def run_pyinstaller(mode: str, console: bool) -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--collect-submodules",
        "flask",
        "--collect-submodules",
        "werkzeug",
        "--collect-submodules",
        "requests",
    ]
    command.append("--console" if console else "--windowed")
    command.append("--onefile" if mode == "onefile" else "--onedir")
    command.append(str(ROOT / "main.py"))
    subprocess.check_call(command, cwd=ROOT)


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def prepare_stage(mode: str) -> Path:
    stage_dir = RELEASE_DIR / APP_NAME
    safe_rmtree(stage_dir) if stage_dir.exists() else None
    stage_dir.mkdir(parents=True, exist_ok=True)

    if mode == "onedir":
        copy_tree(DIST_DIR / APP_NAME, stage_dir)
    else:
        shutil.copy2(DIST_DIR / f"{APP_NAME}.exe", stage_dir / f"{APP_NAME}.exe")

    # config.json is intentionally outside the exe so users can edit it and the
    # GUI can save changes immediately.
    shutil.copy2(ROOT / "config.example.json", stage_dir / "config.example.json")
    shutil.copy2(ROOT / "config.example.json", stage_dir / "config.json")
    shutil.copy2(ROOT / "README.md", stage_dir / "README.md")
    return stage_dir


def zip_stage(stage_dir: Path, mode: str) -> Path:
    zip_path = RELEASE_DIR / f"{APP_NAME}-windows-{mode}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file_path in stage_dir.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(RELEASE_DIR))
    return zip_path


def main() -> None:
    args = parse_args()
    if not args.skip_clean:
        safe_rmtree(BUILD_DIR)
        safe_rmtree(DIST_DIR)
        safe_rmtree(RELEASE_DIR)
        if SPEC_FILE.exists():
            SPEC_FILE.unlink()
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    ensure_pyinstaller(args.install_missing)
    run_pyinstaller(args.mode, args.console)
    stage_dir = prepare_stage(args.mode)
    zip_path = zip_stage(stage_dir, args.mode)
    if SPEC_FILE.exists():
        SPEC_FILE.unlink()
    print(f"Built package: {zip_path}")


if __name__ == "__main__":
    main()
