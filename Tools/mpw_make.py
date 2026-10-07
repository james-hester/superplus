import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

import mpw
from paths import source_path


TOOLS = Path(__file__).resolve().parent
FINAL = "MacPlus-v3.hiram.bin"
UNFINISHED = "MacPlus-v3.unfinished.bin"
LINKED = "MacPlus-v3.rom"
MAP = "MacPlus-v3.map"
STATE = "mpw-build.json"
LAYOUT_SOURCES = ["dispatch-placeholder.a", "rom-prefix-end.a", "rom-build-info.a"]
SIZE_FILE = "DispatchSize.a"
STATUS_FILE = "DispatchStatus"
LAYOUT_BYTES = 28
DIAGNOSTIC_ERROR = re.compile(
    r"#\s*(?:Fatal\s+error|Error)\s*:|###.*(?:Errors prevented|Execution.*Terminated)|"
    r"###\s*Error\s+\d+\s*###|###.*(?:Link|Asm|SC):\s*Error|Make - Execution terminated", re.I)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def quote(value):
    value = str(value)
    if any(char in value for char in "\r\n\0"):
        raise ValueError("MPW arguments must fit one line")
    value = value.replace("∂", "∂∂")
    for char in ('"', "{", "}", "`"):
        value = value.replace(char, "∂" + char)
    return '"' + value + '"'


def prepare_resource(build, module):
    name = module["name"]
    flags = int(module["block_flags"], 16)
    pointer = int(module["first_master_pointer_offset"], 16)
    lines = [f"rom_{name.replace('-', '_')} {flags} {pointer} {len(module['resources'])}"]
    attribute_bits = {"sysheap": 64, "purgeable": 32, "locked": 16,
                      "protected": 8, "preload": 4, "changed": 2}
    for item in module["resources"]:
        kind = item["type"].encode("mac_roman")
        label = item["label"]
        attributes = item["attributes"]
        identifier = item["id"]
        resource_name = (item.get("name") or "").encode("mac_roman")
        if (len(kind) != 4 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", label)
                or not isinstance(identifier, int) or not -32768 <= identifier <= 32767
                or len(resource_name) > 255 or len(set(attributes)) != len(attributes)
                or set(attributes) - attribute_bits.keys()):
            raise ValueError(f"Invalid resource layout item: {item}")
        bits = sum(attribute_bits[value] for value in attributes)
        lines.append(f"{kind.hex()} {identifier} {bits} {label} {resource_name.hex() or '-'}")
    mpw.stage(build / (name + ".r"), source_path(module["source"]).read_text())
    mpw.stage(build / (name + ".layout"), "\n".join(lines) + "\n")


def resource_commands(name, packer="rombuild"):
    return [("Rez", name + ".r", "-o", name + ".rsrc"),
            (packer, "--resources", name + ".layout", name + ".rsrc", name + ".a")]


def resource_assembly(module, build, runner):
    build = Path(build).resolve() / "resources" / module["name"]
    build.mkdir(parents=True, exist_ok=True)
    prepare_resource(build, module)
    tool = mpw.build_tool("rombuild", build)
    for command in resource_commands(module["name"], str(tool["executable"])):
        mpw.run(runner, command[0], command[1:], build)
    return (build / (module["name"] + ".a")).read_bytes().decode("mac_roman").replace("\r", "\n")


def layout(modules, postlink):
    modules = list(modules)
    if not modules:
        raise ValueError("MPW build requires assembly modules")
    names = [module["name"] for module in modules]
    if len(names) != len(set(names)) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in names):
        raise ValueError("MPW module names must be unique filenames")
    dispatch = [module for module in modules if module.get("format") == "mpw-compressed-dispatch"]
    if len(dispatch) != 1:
        raise ValueError("MPW build requires one dispatch table")
    size = postlink["rom_size"]
    if postlink["tool"] != "hiram" or not isinstance(size, int) or size <= 0 or size % 1024:
        raise ValueError("MPW build requires Hiram and a ROM size in whole KiB")
    fill_start = int(postlink["fill_start"], 16)
    if not 4 <= fill_start < size:
        raise ValueError("Hiram fill start lies outside the ROM")
    return modules, dispatch[0]["name"], size, fill_start


def assembly_dependencies(build, name):
    manifest = mpw.input_manifest(Path(build) / (name + ".a"))
    return json.loads(manifest.read_text()) if manifest.is_file() else {"files": [], "dependencies": {}}


def write_makefile(build, modules, postlink):
    build = Path(build).resolve()
    build.mkdir(parents=True, exist_ok=True)
    modules, dispatch_name, size, fill_start = layout(modules, postlink)
    objects = ["dispatch-placeholder.o" if module["name"] == dispatch_name else module["name"] + ".o"
               for module in modules]
    objects += ["rom-prefix-end.o", dispatch_name + ".o", "rom-build-info.o"]
    prerequisites = [module["name"] + ".o" for module in modules] + ["rom-prefix-end.o", "rom-build-info.o"]
    libraries = ['"' + name + '"' for name in mpw.C_LIBRARIES]
    lines = [
        f'{quote(FINAL)} ƒ {quote(UNFINISHED)} "hiram" "Makefile"',
        f'\tExecute {quote(STATUS_FILE)}',
        f'\thiram -s {size // 1024} -i {quote(postlink["initials"])} '
        f'-fd {quote(postlink["date"])} --fill-start {{ROMPrefixSize}} {quote(UNFINISHED)} {quote(FINAL)}',
        "",
        f'{quote(UNFINISHED)} ƒ "Makefile" "rombuild" "dispatch-placeholder.a" {quote(SIZE_FILE)} ∂',
        "\t" + " ∂\n\t".join(quote(name) for name in prerequisites),
        "\tSet DispatchChanged 1",
        "\tFor DispatchPass In " + " ".join(str(number) for number in range(1, 17)),
        "\t\tIf {DispatchChanged} != 0",
        '\t\t\tAsm -sym on,nolines -wb -l -o "dispatch-placeholder.o" "dispatch-placeholder.a"',
        f'\t\t\tLink -t ZROM -rt "ROM =0" -la -o {quote(LINKED)} ∂',
        "\t\t\t\t" + " ∂\n\t\t\t\t".join(quote(name) for name in objects) + f" > {quote(MAP)}",
        f'\t\t\trombuild --resolve-layout {quote(SIZE_FILE)} --status-file {quote(STATUS_FILE)} '
        f'--rom-size {size} {quote(LINKED)} {quote(UNFINISHED)}',
        f'\t\t\tExecute {quote(STATUS_FILE)}',
        "\t\tEnd",
        "\tEnd",
        "\tIf {DispatchChanged} != 0",
        '\t\tEcho "Dispatch layout did not converge after 16 links"',
        "\t\tExit 1",
        "\tEnd",
        "",
    ]
    for name in [module["name"] for module in modules] + ["rom-prefix-end", "rom-build-info"]:
        inputs = assembly_dependencies(build, name)["files"]
        prerequisites = [quote(name + ".a"), '"Makefile"']
        prerequisites.extend(quote(":" + path.replace("/", ":")) for path in inputs)
        lines.extend([
            f'{quote(name + ".o")} ƒ ' + " ∂\n\t".join(prerequisites),
            f'\tAsm -sym on,nolines -wb -l -i {quote(mpw.ASM_INCLUDE_PATH)} '
            f'-o {quote(name + ".o")} {quote(name + ".a")} > {quote(name + ".listing.txt")}',
            "",
        ])
    for module in modules:
        if module.get("format") != "rez-data":
            continue
        name = module["name"]
        rez, pack = resource_commands(name)
        lines.extend([
            f'{quote(name + ".rsrc")} ƒ {quote(name + ".r")} "Makefile"',
            "\t" + " ".join(quote(value) for value in rez),
            "",
            f'{quote(name + ".a")} ƒ {quote(name + ".rsrc")} {quote(name + ".layout")} "rombuild" "Makefile"',
            "\t" + " ".join(quote(value) for value in pack),
            "",
        ])
    for tool in ("rombuild", "hiram"):
        compile_command, link_command = mpw.c_tool_commands(tool, mpw.C_LIBRARIES)
        compile_line = " ".join(quote(argument) for argument in compile_command)
        link_line = " ".join('"' + argument + '"' if argument in mpw.C_LIBRARIES else quote(argument)
                             for argument in link_command)
        lines.extend([
            f'{quote(tool + ".c.o")} ƒ {quote(tool + ".c")} "Makefile"',
            "\t" + compile_line,
            "",
            f'{quote(tool)} ƒ {quote(tool + ".c.o")} "Makefile" ' + " ".join(libraries),
            "\t" + link_line,
            "",
        ])
    path = build / "Makefile"
    mpw.stage(path, "\n".join(lines) + "\n")
    return path


def fingerprints(path):
    path = Path(path)
    result = {"data_sha256": digest(path.read_bytes())}
    try:
        resource = (path / "..namedfork/rsrc").read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        resource = b""
    if resource:
        result["resource_sha256"] = digest(resource)
    return result


def remove_outputs(build, names):
    for name in names:
        (build / name).unlink(missing_ok=True)


def prepare_project(build, modules, postlink):
    build = Path(build)
    makefile = write_makefile(build, modules, postlink)
    helpers = {
        "dispatch-placeholder.a": """rom_dispatch_table PROC EXPORT
    EXPORT DispTable,rom_dispatch_table_end
    INCLUDE 'DispatchSize.a'
DispTable EQU *
    DCB.B DispatchBytes,0
rom_dispatch_table_end EQU *
    ENDP
    END
""",
        "rom-prefix-end.a": """rom_prefix_end PROC EXPORT
    ENDP
    END
""",
        "rom-build-info.a": """rom_build_info PROC EXPORT
    IMPORT BaseOfROM,rom_dispatch_table,rom_dispatch_table_end
    IMPORT rom_dispatch_offsets,rom_prefix_end
    DC.L $52424c44,1
    DC.L rom_dispatch_table-BaseOfROM
    DC.L rom_dispatch_table_end-BaseOfROM
    DC.L rom_dispatch_offsets-BaseOfROM
    DC.L rom_prefix_end-BaseOfROM
    DC.L 768
    ENDP
    END
""",
    }
    for name, text in helpers.items():
        mpw.stage(build / name, text)
    if not (build / SIZE_FILE).exists():
        mpw.stage(build / SIZE_FILE, "DispatchBytes EQU 770\n")
    for tool in ("rombuild", "hiram"):
        source = (TOOLS / (tool + ".c")).read_text()
        mpw.stage(build / (tool + ".c"), source)
    for module in modules:
        if module.get("format") == "rez-data":
            prepare_resource(build, module)
    return makefile


def linked_layout(build):
    data = mpw.resource_data(Path(build) / LINKED)
    if len(data) < LAYOUT_BYTES:
        raise ValueError("Linked ROM omits layout metadata")
    magic, version, start, end, offsets, prefix_end, count = struct.unpack(">7I", data[-LAYOUT_BYTES:])
    if (magic, version, count) != (0x52424c44, 1, 768):
        raise ValueError("Invalid linked layout metadata")
    symbols = mpw.link_map(Path(build) / MAP)
    expected = {"rom_dispatch_table": start, "rom_dispatch_table_end": end,
                "rom_dispatch_offsets": offsets, "rom_prefix_end": prefix_end,
                "rom_build_info": len(data) - LAYOUT_BYTES}
    if any(symbols.get(name) != value for name, value in expected.items()):
        raise ValueError("Link map differs from linked layout metadata")
    if not (4 <= start < end <= prefix_end == offsets and offsets + 3072 + LAYOUT_BYTES == len(data)):
        raise ValueError("Invalid linked layout bounds")
    return {"dispatch_offset": start, "dispatch_end": end, "offsets_start": offsets,
            "prefix_end": prefix_end, "metadata_start": len(data) - LAYOUT_BYTES,
            "metadata_bytes": LAYOUT_BYTES, "linked_bytes": len(data)}


def build_project(build, modules, postlink):
    build = Path(build).resolve()
    build.mkdir(parents=True, exist_ok=True)
    modules, dispatch_name, size, fill_start = layout(modules, postlink)
    runner = mpw.executable()
    make = mpw.executable("mpw-make", "MPW_MAKE_EXECUTABLE", runner.parent / "mpw-make")
    installation = mpw.installation()
    environment = os.environ.copy()
    runner_directory = build / ".mpw-runner"
    runner_directory.mkdir(exist_ok=True)
    runner_link = runner_directory / "mpw"
    if runner_link.is_symlink() and runner_link.resolve() != runner.resolve():
        runner_link.unlink()
    if not runner_link.exists():
        runner_link.symlink_to(runner)
    environment["PATH"] = str(runner_directory) + os.pathsep + environment.get("PATH", "")
    environment["MPW"] = str(installation)
    makefile = prepare_project(build, modules, postlink)
    resources = [module["name"] for module in modules if module.get("format") == "rez-data"]
    source_names = [module["name"] + suffix for module in modules
                    for suffix in ((".r", ".layout") if module["name"] in resources else (".a",))]
    source_names += LAYOUT_SOURCES + ["rombuild.c", "hiram.c", "Makefile"]
    assembly_inputs = {}
    original_dependencies = {}
    for module in modules:
        name = module["name"]
        inputs = assembly_dependencies(build, name)
        if inputs["files"]:
            paths = inputs["files"] + [mpw.input_manifest(name + ".a").name]
            assembly_inputs[name] = set(paths)
            source_names.extend(paths)
            for source, expected in inputs["dependencies"].items():
                if source in original_dependencies and original_dependencies[source] != expected:
                    raise ValueError(f"Source changed after preparation: {source}")
                original_dependencies[source] = expected
    source_names = sorted(set(source_names))
    mpw.validate_dependencies(original_dependencies)
    sources = {name: digest((build / name).read_bytes()) for name in source_names}
    tool_paths = [runner, make, *[installation / "Tools" / name for name in ("Make", "Asm", "SC", "Link", "Rez")],
                  *mpw.c_libraries()]
    tools = {str(path): fingerprints(path) for path in tool_paths}
    state_path = build / STATE
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    changed = [name for name in sources if sources[name] != previous.get("sources", {}).get(name)]
    tool_change = tools != previous.get("tools")
    all_objects = [module["name"] + ".o" for module in modules] + [name[:-2] + ".o" for name in LAYOUT_SOURCES] + ["hiram.c.o", "rombuild.c.o"]
    listing_objects = {name + ".lst": name[:-2] + ".o" for name in [module["name"] + ".a" for module in modules] + LAYOUT_SOURCES}
    output_names = [FINAL, UNFINISHED, LINKED, MAP, SIZE_FILE, STATUS_FILE, "hiram", "rombuild", *all_objects, *listing_objects]
    resource_outputs = [name + suffix for name in resources for suffix in (".rsrc", ".a")]
    output_names += resource_outputs
    if tool_change or "Makefile" in changed:
        remove_outputs(build, all_objects + ["hiram", "rombuild"] + resource_outputs)
    else:
        for name, inputs in assembly_inputs.items():
            if inputs.intersection(changed):
                remove_outputs(build, [name + ".o"])
        for name in changed:
            if name.endswith(".a") and "/" not in name:
                remove_outputs(build, [name[:-2] + ".o"])
            elif name.endswith(".c"):
                remove_outputs(build, [name + ".o", name[:-2]])
                if name == "rombuild.c":
                    remove_outputs(build, [part + suffix for part in resources for suffix in (".a", ".o")])
            elif name.endswith((".r", ".layout")):
                stem = name.rsplit(".", 1)[0]
                remove_outputs(build, [stem + suffix for suffix in (".rsrc", ".a", ".o")])
    if changed or tool_change:
        remove_outputs(build, [FINAL, UNFINISHED, LINKED, MAP])
    invalid_outputs = [name for name in output_names if not (build / name).exists()
                       or fingerprints(build / name) != previous.get("outputs", {}).get(name)]
    if invalid_outputs:
        invalid_objects = [listing_objects[name] for name in invalid_outputs if name in listing_objects]
        for name in invalid_outputs:
            if name in resource_outputs:
                stem = name.rsplit(".", 1)[0]
                invalid_objects.extend(stem + suffix for suffix in (".a", ".o"))
            elif name in {"rombuild", "rombuild.c.o"}:
                invalid_objects.extend(part + suffix for part in resources for suffix in (".a", ".o"))
        remove_outputs(build, [*[name for name in invalid_outputs if name != SIZE_FILE], *invalid_objects, FINAL, UNFINISHED, LINKED, MAP])
        if SIZE_FILE in invalid_outputs:
            mpw.stage(build / SIZE_FILE, "DispatchBytes EQU 770\n")
    command = [str(make), "-f", makefile.name, FINAL]
    result = subprocess.run(command, cwd=build, env=environment, capture_output=True)
    stdout = result.stdout.decode("mac_roman")
    stderr = result.stderr.decode("mac_roman")
    (build / "mpw-make.stdout.log").write_text(stdout)
    (build / "mpw-make.stderr.log").write_text(stderr)
    try:
        if result.returncode or DIAGNOSTIC_ERROR.search(stdout + "\n" + stderr):
            raise RuntimeError(f"MPW Make failed ({result.returncode}):\n{stdout}\n{stderr}")
        resolved_layout = linked_layout(build)
        if (build / FINAL).stat().st_size != size or (build / UNFINISHED).stat().st_size != resolved_layout["prefix_end"]:
            raise ValueError("MPW Make produced an unexpected image length")
        if not (build / LINKED / "..namedfork/rsrc").read_bytes():
            raise ValueError("MPW Link did not produce a ROM resource")
        if sources != {name: digest((build / name).read_bytes()) for name in source_names}:
            raise ValueError("MPW source changed during the build")
        mpw.validate_dependencies(original_dependencies)
        outputs = {name: fingerprints(build / name) for name in output_names}
    except Exception:
        remove_outputs(build, [FINAL, UNFINISHED, LINKED, STATE])
        raise
    provenance = {"tool": "MPW Make", "command": command, "directory": str(build),
                  "emulator": str(runner), "installation": str(installation),
                  "sources": sources, "tools": tools, "outputs": outputs,
                  "dispatch_offset": hex(resolved_layout["dispatch_offset"]), "layout": resolved_layout, "settings": dict(postlink),
                  "stdout_path": str(build / "mpw-make.stdout.log"),
                  "stderr_path": str(build / "mpw-make.stderr.log"),
                  "map_path": str(build / MAP), "map_sha256": digest((build / MAP).read_bytes())}
    state_path.write_text(json.dumps(provenance, indent=2) + "\n")
    return provenance
