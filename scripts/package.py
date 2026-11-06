"""Stage separate Dify Tool and Trigger packages from one maintained source tree."""

import argparse
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMMON = [
    "main.py",
    "linq_client.py",
    "README.md",
    "PRIVACY.md",
    "VALIDATION.md",
    "LICENSE",
    "requirements.txt",
    "_assets",
]
SOURCES = {
    "linq": ["provider/__init__.py", "provider/linq.py", "provider/linq.yaml", "tools"],
    "linq_trigger": [
        "provider/__init__.py",
        "provider/linq_trigger.py",
        "provider/linq_trigger.yaml",
        "events",
        "webhooks.py",
    ],
}


def stage_plugin(name: str, destination: Path) -> Path:
    """Copy only runtime files; never delete an existing directory."""
    destination.mkdir(parents=True, exist_ok=False)
    for relative in COMMON + SOURCES[name]:
        source, target = ROOT / relative, destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(source, target)
    shutil.copy2(ROOT / "manifests" / f"{name}.yaml", destination / "manifest.yaml")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, help="Path to the Dify plugin CLI")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    for name in SOURCES:
        staged = stage_plugin(name, args.output / name)
        manifest = yaml.safe_load((staged / "manifest.yaml").read_text())
        package = args.output / f"{name}-{manifest['version']}.difypkg"
        subprocess.run([args.cli, "plugin", "package", str(staged), "-o", str(package)], check=True)
        print(package)


if __name__ == "__main__":
    main()
