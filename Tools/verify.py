#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
from dispatch_table import encode_dispatch_table, decode_dispatch_table, TOOLBOX_COUNT, OS_COUNT
import mpw
from mpw_make import build_project, resource_assembly


from paths import HERE, source_path, inventory_record

ROOT = HERE
INCLUDE = re.compile(r"\s+INCLUDE\s+'([^']+)'\s*(?:;.*)?", re.I)
SHARED_INCLUDES = HERE / "Source" / "Includes"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class AssemblyText(str):
    def __new__(cls, text, dependencies, input_files=None, input_sources=None):
        result = super().__new__(cls, text)
        result.dependencies = dependencies
        result.input_files = input_files or {}
        result.input_sources = input_sources or {}
        return result


def assembly_inputs(source):
    source = source.resolve()
    dependencies, contents = {}, {}
    pending = [source]
    while pending:
        path = pending.pop().resolve()
        if path in contents:
            continue
        data = path.read_bytes()
        contents[path] = data.decode("utf-8")
        dependencies[str(path)] = sha256(data)
        for line in contents[path].splitlines():
            match = INCLUDE.fullmatch(line)
            if match:
                name = match[1]
                if name.startswith(":"):
                    name = name[1:]
                name = name.replace(":", "/")
                candidates = [directory / name for directory in (path.parent, SHARED_INCLUDES)]
                child = next((candidate for candidate in candidates if candidate.is_file()), None)
                if child is not None:
                    pending.append(child)
            elif re.match(r"\s+INCLUDE\b", line, re.I):
                for directory in (path.parent, SHARED_INCLUDES):
                    pending.extend(directory.glob("*.a"))
    external = [path.parent for path in contents
                if not path.is_relative_to(HERE) and not path.is_relative_to(SHARED_INCLUDES)]
    external_root = Path(os.path.commonpath(external)) if external else None
    external_id = sha256(str(external_root).encode())[:12] if external_root else None

    def staged_path(path):
        if path.is_relative_to(SHARED_INCLUDES):
            return Path("Inputs/Source/Includes") / path.relative_to(SHARED_INCLUDES)
        if path.is_relative_to(HERE):
            return Path("Inputs") / path.relative_to(HERE)
        return Path("Inputs/External") / external_id / path.relative_to(external_root)

    files = {staged_path(path).as_posix(): text for path, text in contents.items()}
    origins = {staged_path(path).as_posix(): str(path) for path in contents}
    return staged_path(source), dependencies, files, origins


def translate(source, module_name="ROMModule"):
    path, dependencies, input_files, input_sources = assembly_inputs(source)
    marker = f"{module_name} PROC EXPORT\n\tENDP\n"
    include = ":" + str(path).replace("/", ":")
    text = marker + "\tMACHINE MC68000\n\tSTRING ASIS\n\tOPT SYNON\n"
    return AssemblyText(text + f"\tINCLUDE '{include}'\n", dependencies, input_files, input_sources)


def module_assembly(module):
    source = source_path(module["source"])
    name = module["name"]
    source_format = module.get("format", "mpw-asm")
    module_name = "rom_" + name.replace("-", "_")
    if source_format == "mpw-compressed-dispatch":
        module_name = "rom_dispatch_offsets"
    if source_format in {"mpw-asm", "mpw-compressed-dispatch"}:
        translated = translate(source, module_name=module_name)
    else:
        raise ValueError(f"{name}: unsupported source format {source_format}")
    return translated


def project_assemblies(modules):
    return {module["name"]: module_assembly(module) for module in modules
            if module.get("format") != "rez-data"}


def verify_module(module, rom, base, runner, build):
    if module.get("format") == "rez-data":
        source = source_path(module["source"]).resolve()
        dependencies = {str(source): sha256(source.read_bytes())}
        translated = AssemblyText(resource_assembly(module, build, runner), dependencies)
    else:
        translated = module_assembly(module)
    actual, offsets = mpw.assemble(translated, module["name"], runner, build)
    return verify_emitted(module, actual, offsets, translated, rom, base, build)


def verify_emitted(module, actual, offsets, translated, rom, base, build, linked_symbols=None):
    source = source_path(module["source"])
    name = module["name"]
    dependencies = getattr(translated, "dependencies", {})
    if any(sha256(Path(path).read_bytes()) != digest for path, digest in dependencies.items()):
        raise ValueError(f"Source changed during the build: {name}")
    start, end = int(module["start"], 16), int(module["end_exclusive"], 16)
    source_format = module.get("format", "mpw-asm")
    symbols = {name: base + value for name, value in (linked_symbols or {}).items()}
    symbols.update({name: start + value for name, value in offsets.items()})
    binary = build / (name + ".bin")
    binary.write_bytes(actual)
    dispatch_result = None
    if source_format == "mpw-compressed-dispatch":
        uncompressed = actual
        (build / (name + ".uncompressed.bin")).write_bytes(uncompressed)
        actual = encode_dispatch_table(uncompressed, len(rom))
        decoded, positions = decode_dispatch_table(actual, len(rom))
        if decoded != uncompressed:
            raise ValueError(f"{name}: dispatch compression changed the decoded offsets")
        binary.write_bytes(actual)
        dispatch_result = {"uncompressed_bytes": len(uncompressed),
                           "uncompressed_sha256": sha256(uncompressed),
                           "toolbox_entries": TOOLBOX_COUNT, "os_entries": OS_COUNT,
                           "os_table_address": hex(start + positions[TOOLBOX_COUNT])}
    if not base <= start < end <= base + len(rom):
        raise ValueError(f"{name}: span lies outside ROM")
    expected = rom[start - base:end - base]
    pending_checksum = module.get("postlink_checksum", False)
    if pending_checksum:
        if start != base or len(actual) < 4 or actual[:4] != bytes(4):
            raise ValueError(f"{name}: postlink checksum must be a zero longword at the ROM base")
        expected = bytes(4) + expected[4:]
    if actual != expected:
        differing = [(hex(start + i), a, b) for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
        raise ValueError(f"{name}: assembled {len(actual)} bytes, expected {len(expected)}; "
                         f"first mismatches (address, assembled, ROM): {differing[:12]}")
    for label, address in module.get("entry_points", {}).items():
        if symbols.get(label.lower()) != int(address, 16):
            raise ValueError(f"{name}: entry point {label} does not equal {address}")
    result = {"name": name, "source": module["source"],
              "source_sha256": dependencies.get(str(source.resolve()), sha256(source.read_bytes())),
              "start": module["start"], "end_exclusive": module["end_exclusive"],
              "bytes": len(actual), "sha256": sha256(actual), "matches_rom": not pending_checksum,
              "verified_bytes": len(actual) - (4 if pending_checksum else 0)}
    if pending_checksum:
        result["postlink_checksum"] = True
    if dispatch_result is not None:
        result["dispatch_table"] = dispatch_result
    if dependencies:
        result["source_dependencies"] = [
            {"path": str(Path(path).relative_to(ROOT)) if Path(path).is_relative_to(ROOT) else path,
             "sha256": digest} for path, digest in sorted(dependencies.items())]
    return result


def build_image(modules, rom, base, build, postlink=None):
    output = build / "MacPlus-v3.rebuilt.bin"
    output.unlink(missing_ok=True)
    position = base
    gaps = []
    parts = []
    for module in sorted(modules, key=lambda item: int(item["start"], 16)):
        start, end = int(module["start"], 16), int(module["end_exclusive"], 16)
        if not base <= start < end <= base + len(rom):
            raise ValueError(f"{module['name']}: image span lies outside ROM")
        if start < position:
            raise ValueError(f"{module['name']}: image spans overlap")
        if start > position:
            gaps.append({"start": hex(position), "end_exclusive": hex(start), "bytes": start - position})
        part = (build / (module["name"] + ".bin")).read_bytes()
        if len(part) != end - start or sha256(part) != module["sha256"]:
            raise ValueError(f"{module['name']}: binary changed after verification")
        parts.append(part)
        position = end
    if position < base + len(rom):
        gaps.append({"start": hex(position), "end_exclusive": hex(base + len(rom)),
                     "bytes": base + len(rom) - position})
    if postlink is not None:
        fill_start = int(postlink["fill_start"], 16)
        if postlink["rom_size"] != len(rom) or not 4 <= fill_start < len(rom):
            raise ValueError("Hiram span lies outside the target ROM")
        tail = {"start": hex(base + fill_start), "end_exclusive": hex(base + len(rom)),
                "bytes": len(rom) - fill_start}
        if position > base + fill_start:
            raise ValueError("An assembled module overlaps the Hiram fill span")
        if gaps == [tail]:
            gaps = []
    if gaps:
        return {"complete": False, "gaps": gaps}
    image = b"".join(parts)
    postlink_result = None
    if postlink is not None:
        if postlink["tool"] != "hiram" or image[:4] != bytes(4):
            raise ValueError("Hiram requires a zero checksum placeholder")
        if (build / "MacPlus-v3.unfinished.bin").read_bytes() != image:
            raise ValueError("MPW ROMBuild changed the verified module bytes")
        finished = (build / "MacPlus-v3.hiram.bin").read_bytes()
        if finished[4:len(image)] != image[4:]:
            raise ValueError("MPW Hiram changed assembled bytes outside the checksum")
        postlink_result = {"tool": "MPW Hiram", "settings": dict(postlink),
                           "input_sha256": sha256(image), "output_sha256": sha256(finished),
                           "generated_spans": [{"offset": "0x0", "bytes": 4},
                                               {"offset": hex(fill_start), "bytes": len(rom) - fill_start}]}
        image = finished
    elif any(module.get("postlink_checksum") for module in modules):
        raise ValueError("A checksum placeholder requires Hiram")
    if image != rom:
        raise ValueError("The rebuilt image differs from the reference ROM.")
    checksum = sum(int.from_bytes(image[i:i + 2], "big") for i in range(4, len(image), 2)) & 0xffffffff
    if checksum != int.from_bytes(image[:4], "big"):
        raise ValueError("The rebuilt image checksum does not match.")
    output.write_bytes(image)
    if output.read_bytes() != image:
        output.unlink(missing_ok=True)
        raise ValueError("The rebuilt image changed while being written.")
    result = {"complete": True, "path": str(output.resolve()), "bytes": len(image),
              "sha256": sha256(image), "checksum": hex(checksum), "matches_rom": True, "gaps": []}
    if postlink_result is not None:
        result["postlink"] = postlink_result
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=HERE / "target.json")
    parser.add_argument("--build", type=Path, default=HERE / "Build")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    args.build = args.build.resolve()
    args.build.mkdir(parents=True, exist_ok=True)
    report = args.build / "verification.json"
    report.unlink(missing_ok=True)
    (args.build / "MacPlus-v3.rebuilt.bin").unlink(missing_ok=True)
    target = json.loads(args.target.read_text())
    rom = source_path(target["rom"]["path"]).read_bytes()
    if len(rom) != target["rom"]["size"] or sha256(rom) != target["rom"]["sha256"]:
        raise ValueError("The reference ROM differs from the recorded target.")
    checksum = sum(int.from_bytes(rom[i:i + 2], "big") for i in range(4, len(rom), 2)) & 0xffffffff
    if checksum != int.from_bytes(rom[:4], "big") or checksum != int(target["rom"]["checksum"], 16):
        raise ValueError("The ROM checksum does not match.")
    historical_sources = []
    for inventory in ("source-inventory.json", "resource-source-inventory.json"):
        historical_sources.extend(inventory_record(item) for item in
                                  json.loads((HERE / "Evidence" / inventory).read_text()))
    mpw_interfaces = json.loads((HERE / "Evidence/mpw-1.0.1-includes.json").read_text())
    historical_sources.extend(inventory_record(item, root=HERE)
                              for item in mpw_interfaces["files"])
    base = int(target["rom"]["base_address"], 16)
    modules = list(target["modules"])
    covered = set()
    for module in modules:
        addresses = set(range(int(module["start"], 16), int(module["end_exclusive"], 16)))
        if covered & addresses:
            raise ValueError(f"Overlapping module span: {module['name']}")
        covered.update(addresses)
    fill_start = int(target.get("postlink", {}).get("fill_start", "0"), 16)
    complete = covered == set(range(base, base + fill_start))
    build_record = None
    verified = []
    if complete:
        translated = project_assemblies(modules)
        for name, text in translated.items():
            mpw.stage(args.build / (name + ".a"), text)
        resource_dependencies = {
            module["name"]: {str(source_path(module["source"]).resolve()):
                             sha256(source_path(module["source"]).read_bytes())}
            for module in modules if module.get("format") == "rez-data"}
        if args.prepare_only:
            from mpw_make import prepare_project
            makefile = prepare_project(args.build, modules, target["postlink"])
            print(f"Prepared MPW sources and {makefile}.")
            return
        print("Building ROM with MPW Make, Asm, Rez, Link, SC, ROMBuild, and Hiram.", flush=True)
        build_record = build_project(args.build, modules, target["postlink"])
        for name, dependencies in resource_dependencies.items():
            if any(sha256(Path(path).read_bytes()) != digest for path, digest in dependencies.items()):
                raise ValueError(f"Resource source changed during the build: {name}")
            text = (args.build / (name + ".a")).read_bytes().decode("mac_roman").replace("\r", "\n")
            translated[name] = AssemblyText(text, dependencies)
        linked = mpw.resource_data(args.build / "MacPlus-v3.rom")
        locations = mpw.link_map(args.build / "MacPlus-v3.map")
        for first, second in target.get("link_equalities", []):
            if (locations.get(first.lower()) is None
                    or locations.get(first.lower()) != locations.get(second.lower())):
                raise ValueError(f"MPW Link separated required adjacent symbols: {first}, {second}")
        position = 0
        dispatch = None
        for module in modules:
            name = module["name"]
            module_name = "rom_" + name.replace("-", "_")
            is_dispatch = module.get("format") == "mpw-compressed-dispatch"
            if is_dispatch:
                module_name = "rom_dispatch_table"
                dispatch = module
            if locations.get(module_name) != position or position + base != int(module["start"], 16):
                raise ValueError(f"MPW Link changed module order or position: {name}")
            offsets, size = mpw.listing_symbols(args.build / (name + ".a.lst"), locations,
                                               locations["rom_dispatch_offsets"] if is_dispatch else position)
            data_start = locations["rom_dispatch_offsets"] if is_dispatch else position
            actual = linked[data_start:data_start + size]
            result = verify_emitted(module, actual, offsets, translated[name], rom, base, args.build, locations)
            position += result["bytes"]
            verified.append(result)
        metadata = (0x52424c44, 1, int(dispatch["start"], 16) - base,
                    int(dispatch["end_exclusive"], 16) - base, position, position, 768)
        if (locations.get("rom_prefix_end") != position
                or locations.get("rom_dispatch_offsets") != position
                or locations.get("rom_build_info") != position + 768 * 4
                or len(linked) != position + 768 * 4 + 28
                or linked[-28:] != struct.pack(">7I", *metadata)):
            raise ValueError("MPW Link emitted unexpected dispatch data or layout metadata")
    else:
        if args.prepare_only:
            raise ValueError("Preparing an MPW Makefile requires the complete target")
        runner = mpw.executable()
        for module in modules:
            verified.append(verify_module(module, rom, base, runner, args.build))
    image = build_image(verified, rom, base, args.build, target.get("postlink"))
    verified_bytes = len(rom) if image["complete"] else sum(item["verified_bytes"] for item in verified)
    if args.require_complete and not image["complete"]:
        raise ValueError(f"Complete image required; {len(rom) - verified_bytes:,} bytes remain unverified.")
    results = {"rom_sha256": sha256(rom), "assembler": "MPW Asm",
               "verified_bytes": verified_bytes, "rom_bytes": len(rom),
               "remaining_bytes": len(rom) - verified_bytes, "image": image, "modules": verified,
               "historical_sources": historical_sources}
    if build_record is not None:
        results["build"] = build_record
    report.write_text(json.dumps(results, indent=2) + "\n")
    print(f"Verified {verified_bytes:,} / {len(rom):,} ROM bytes ({100 * verified_bytes / len(rom):.3f}%).")
    if image["complete"]:
        print(f"Rebuilt image: {image['path']} (SHA-256 {image['sha256']}).")


if __name__ == "__main__":
    main()
