#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import re

from paths import HERE, HISTORICAL_ROOT, inventory_bytes


ROOT = HISTORICAL_ROOT
RECONSTRUCTION = HERE
LABEL = re.compile(r"^([A-Za-z_][A-Za-z0-9_.$@]*):?(?:\s+(.*))?$")
EXCLUDED = {"equ", "set", "macro", "record", "procname"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=RECONSTRUCTION / "Evidence")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inventory_path = args.output / "source-inventory.json"
    recorded = json.loads(inventory_path.read_text()) if inventory_path.exists() else None
    if recorded is None:
        paths = [path for path in sorted(ROOT.rglob("*.a")) if RECONSTRUCTION not in path.parents]
    else:
        paths = [ROOT / item["path"] for item in recorded]
    expected = {item["path"]: item["sha256"] for item in recorded or []}
    labels = defaultdict(list)
    inventory = []
    for path in paths:
        relative = str(path.relative_to(ROOT))
        data = (path.read_bytes() if recorded is None else
                inventory_bytes({"path": relative, "sha256": expected[relative]}, root=ROOT))
        digest = hashlib.sha256(data).hexdigest()
        inventory.append({"path": relative, "sha256": digest})
        for number, line in enumerate(data.decode("utf-8").splitlines(), 1):
            code = line.split(";", 1)[0].rstrip()
            match = LABEL.fullmatch(code)
            if not match:
                continue
            name, rest = match.groups()
            directive = (rest or "").split(maxsplit=1)[0].lower() if rest else "label"
            if directive in EXCLUDED:
                continue
            labels[name.casefold()].append((relative, number, name, directive))
    rows = []
    with (RECONSTRUCTION / "Evidence/ghidra-symbols.tsv").open() as stream:
        for symbol in csv.DictReader(stream, delimiter="\t"):
            address = int(symbol["address"], 16)
            if not 0x400000 <= address < 0x420000 or symbol["source"] != "USER_DEFINED":
                continue
            name = symbol["name"]
            for key, kind in ((name.casefold(), "exact"), (name.casefold() + "trap", "trap_suffix")):
                for path, number, source_name, directive in labels.get(key, []):
                    rows.append((symbol["address"], name, kind, path, number, source_name, directive))
    with (args.output / "source-candidates.tsv").open("w") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(("rom_address", "rom_label", "match", "source", "line", "source_label", "directive"))
        writer.writerows(sorted(rows))
    if recorded is None:
        inventory_path.write_text(json.dumps(inventory, indent=2) + "\n")
    matched = len({row[0] for row in rows})
    print(f"Indexed {len(inventory)} assembly files; {matched} ROM addresses have source-name candidates.")
    print("These are name matches; instruction comparison must establish equivalence.")
    for path, count in Counter(row[3] for row in rows).most_common(12):
        print(f"{count:4} {path}")


if __name__ == "__main__":
    main()
