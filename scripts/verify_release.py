"""Verify hashes, clean source checks and installation without package downloads."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile


def unpack_source(archive, destination):
    with tarfile.open(archive, "r:gz") as tar:
        files = {}
        prefix = None
        for item in tar.getmembers():
            parts = PurePosixPath(item.name).parts
            if (not item.isfile() or item.size > 10*1024*1024 or len(parts)<2
                    or ".." in parts or PurePosixPath(item.name).is_absolute()):
                raise ValueError("unsafe bundle member")
            if prefix is not None and parts[0] != prefix: raise ValueError("multiple roots")
            prefix = parts[0]
            name = "/".join(parts[1:])
            if name in files: raise ValueError("duplicate member")
            files[name] = tar.extractfile(item).read()
    manifest = json.loads(files.pop("SOURCE-MANIFEST.json"))
    if {name: hashlib.sha256(data).hexdigest() for name,data in files.items()} != manifest["files"]:
        raise ValueError("source manifest mismatch")
    for name, data in files.items():
        path = destination/prefix/name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream: stream.write(data)
    return destination/prefix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--full-check", action="store_true")
    args = parser.parse_args()
    for line in (args.directory/"SHA256SUMS").read_text().splitlines():
        expected,name = line.split("  ")
        if Path(name).name != name or hashlib.sha256((args.directory/name).read_bytes()).hexdigest() != expected:
            raise ValueError("release checksum mismatch")
    wheel, = args.directory.glob("*.whl")
    archive, = args.directory.glob("*.tar.gz")
    with zipfile.ZipFile(wheel) as content:
        names=content.namelist()
        for required in ["genesis_fintech/web/static/index.html", "genesis_fintech/policies/worker.py"]:
            if required not in names: raise ValueError("missing wheel asset")
        if not any(name.endswith("/licenses/LICENSE") for name in names): raise ValueError("missing wheel license")
    env = dict(os.environ, PIP_NO_INDEX="1", PYTHONNOUSERSITE="1")
    env.pop("PYTHONPATH",None)
    with tempfile.TemporaryDirectory(prefix="genesis-release-check-") as tmp:
        root=Path(tmp)
        source=unpack_source(archive,root)
        venv.EnvBuilder(with_pip=True).create(root/"env")
        python=root/"env/bin/python"
        def run(command, cwd=root, extra=None):
            subprocess.run(command,cwd=cwd,env={**env,**(extra or {})},check=True,timeout=180)
        run([str(python),"-m","pip","install","--no-index","--no-deps",str(wheel.resolve())])
        run([str(python),"-I","-m","genesis_fintech","doctor"])
        run([str(python),"-I","-m","genesis_fintech","demo","--seed","42","--config",
             str(source/"configs/interactions.json"),"--output",str(root/"demo")])
        summary=json.loads((root/"demo/summary.json").read_text())
        if (summary["metrics"]["tp"],summary["metrics"]["fp"],summary["metrics"]["fn"]) != (4,0,0):
            raise ValueError("installed wheel demo failed")
        run([str(python),"-I","-m","genesis_fintech","generate-dataset","--spec",
             str(source/"configs/dataset.json"),"--output",str(root/"corpus")])
        run([str(python),"-I","-m","genesis_fintech","validate-trajectories",str(root/"corpus"),
             str(source/"examples/training-v1")])
        run([str(python),"-I","-m","genesis_fintech","collect-trajectories",str(root/"corpus"),
             "--output",str(root/"training")])
        if (root/"training/trajectories.jsonl").read_bytes() != (source/"examples/training-v1/trajectories.jsonl").read_bytes():
            raise ValueError("installed wheel training rollout mismatch")
        if args.full_check:
            run(["make","check", "PYTHON="+str(python)],cwd=source)
    print(json.dumps({"ok":True,"offline_install":True,"clean_source_checks":args.full_check}))


if __name__ == "__main__": main()
