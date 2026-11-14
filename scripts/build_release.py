"""Build a deterministic allowlisted source bundle and an offline wheel.

No git index/archive is consulted. Run with the locked build dependency installed.
"""

import argparse
import gzip
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
FILES = ("README.md", "CONTRIBUTING.md", "AGENTS.md", "LICENSE", "Makefile", "pyproject.toml",
         "requirements.lock", "requirements-build.lock", ".gitignore", ".dockerignore",
         ".gitattributes", ".python-version", "PLAN.md",
         "hyperstudio.org-DESIGN.md", "datasets/public-v1.index.json", "datasets/public-v1.tar.gz",
         "examples/training-v1/manifest.json", "examples/training-v1/initial_observations.jsonl",
         "examples/training-v1/trajectories.jsonl")
PATTERNS = ("src/**/*.py", "src/genesis_fintech/web/static/*", "tests/test_*.py",
            "tests/README.md", "tests/fixtures/*.json", "configs/*.json", "docs/*.md",
            "scripts/*.py", "docker/*.Dockerfile", ".github/workflows/*.yml", ".github/*.md",
            ".github/ISSUE_TEMPLATE/*.md")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_files(root=ROOT):
    paths = set(FILES)
    for pattern in PATTERNS:
        paths.update(path.relative_to(root).as_posix() for path in root.glob(pattern))
    paths.discard("docs/CHAT_HISTORY.md")
    result = {}
    for name in sorted(paths):
        path = root/name
        if not path.is_file() or any((root/Path(*Path(name).parts[:i])).is_symlink()
                                     for i in range(1, len(Path(name).parts)+1)):
            raise ValueError("source bundle requires regular files without symbolic links")
        result[name] = path.read_bytes()
    return result


def build_source(root, destination):
    files = source_files(root)
    version = tomllib.loads(files["pyproject.toml"].decode())["project"]["version"]
    prefix = "genesis-fintech-env-"+version
    manifest = {"version": version, "format": 1, "files": {name: digest(data) for name,data in files.items()}}
    files["SOURCE-MANIFEST.json"] = (json.dumps(manifest, sort_keys=True, indent=2)+"\n").encode()
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=buffer, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(prefix+"/"+name)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                archive.addfile(info, io.BytesIO(data))
    path = destination/(prefix+".tar.gz")
    with path.open("xb") as stream: stream.write(buffer.getvalue())
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if importlib.metadata.version("setuptools") != "79.0.1":
        parser.error("Install requirements-build.lock before release build")
    args.output.mkdir(parents=True, exist_ok=False)
    source = build_source(ROOT, args.output)
    env = dict(os.environ, SOURCE_DATE_EPOCH="0", PYTHONHASHSEED="0", PIP_NO_INDEX="1")
    subprocess.run([sys.executable, "-m", "pip", "wheel", str(ROOT), "--no-deps", "--no-build-isolation",
                    "--no-index", "--wheel-dir", str(args.output.resolve())], env=env, check=True)
    files = [source, *args.output.glob("*.whl")]
    (args.output/"SHA256SUMS").write_text("".join(f"{digest(path.read_bytes())}  {path.name}\n" for path in sorted(files)))
    print(json.dumps({"ok": True, "output": str(args.output), "files": [path.name for path in files]}))


if __name__ == "__main__": main()
