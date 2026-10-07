import hashlib
import os
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
HISTORICAL_ROOT = Path(os.environ.get(
    "SUPER_MARIO_ROOT",
    Path.home() / "src/supermario/base/SuperMarioProj.1994-02-09",
)).expanduser().resolve()

# These inventory entries retain the Contains comments and omit the rest of
# the file headers. The values identify the first retained body line.
_HEADER_BODY_LINE = {
    "OS/HFS/TFSVOL.a": 193,
    "OS/HFS/VSM.a": 50,
}


def source_path(path):
    path = Path(path)
    if path.parts and path.parts[0] == "Reconstruction":
        path = Path(*path.parts[1:])
    return HERE / path


def historical_path(path):
    return HISTORICAL_ROOT / path


def _inventory_source(item, root):
    path = Path(item["path"])
    data = (Path(root) / path).read_bytes()
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 == item["sha256"]:
        return data, actual_sha256, "exact"

    body_line = _HEADER_BODY_LINE.get(path.as_posix())
    if body_line is not None:
        lines = data.splitlines(keepends=True)
        body_index = body_line - 1
        if len(lines) > body_index + 1:
            omitted = lines[:3] + lines[5:body_index]
            comments_only = all(not line.strip() or line.lstrip().startswith(b";")
                                for line in omitted)
            contains = (lines[3].lstrip().startswith(b";") and b"Contains:" in lines[3]
                        and lines[4].lstrip().startswith(b";"))
            boundary = not lines[body_index].strip() and lines[body_index + 1].startswith(b";____")
            if comments_only and contains and boundary:
                projected = b"".join(lines[3:5] + lines[body_index:])
                if hashlib.sha256(projected).hexdigest() == item["sha256"]:
                    return projected, actual_sha256, "header_projection"

    raise ValueError(f"Original source differs from the recorded inventory: {item['path']}")


def inventory_bytes(item, root=None):
    return _inventory_source(item, HISTORICAL_ROOT if root is None else root)[0]


def inventory_record(item, root=None):
    _, actual_sha256, verification = _inventory_source(item, HISTORICAL_ROOT if root is None else root)
    return {
        "path": item["path"],
        "recorded_sha256": item["sha256"],
        "actual_sha256": actual_sha256,
        "verification": verification,
    }
