#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def write_text(path, text):
    data = text.replace("\n", "\r").encode("mac_roman")
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    finder_info = b"TEXTMPS " + bytes(24)
    if hasattr(os, "setxattr"):
        os.setxattr(path, "com.apple.FinderInfo", finder_info)
    else:
        subprocess.run(["xattr", "-wx", "com.apple.FinderInfo", finder_info.hex(), str(path)],
                       check=True)
    return True


def stage(build, root=ROOT):
    build = Path(build).resolve()
    if build == root or root.is_relative_to(build):
        raise ValueError("The build directory must not contain the project sources")
    changed = False
    for directory, suffixes in (("Source", {".a", ".r"}),
                                ("MPW", {".a", ".make", ".layout"}),
                                ("Tools", {".c"})):
        sources = {path.relative_to(root) for path in (root / directory).rglob("*")
                   if path.is_file() and path.suffix in suffixes}
        for relative in sorted(sources):
            changed |= write_text(build / relative, (root / relative).read_text())
        for path in (build / directory).rglob("*"):
            if path.is_file() and path.relative_to(build) not in sources:
                path.unlink()
                changed = True
    if changed or not (build / "SourceStamp").exists():
        (build / "SourceStamp").touch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy MPW inputs as MacRoman text with CR line endings.")
    parser.add_argument("build", type=Path, nargs="?", default=ROOT / "Build")
    stage(parser.parse_args().build)
