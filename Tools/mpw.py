import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

TOOLS = Path(__file__).resolve().parent
C_LIBRARIES = ("{Libraries}MacRuntime.o", "{CLibraries}StdCLib.o",
               "{Libraries}IntEnv.o", "{Libraries}Interface.o")


def executable(name="mpw", variable="MPW_EXECUTABLE", preferred=None):
    configured = os.environ.get(variable)
    candidate = configured or (str(preferred) if preferred and preferred.is_file() else None)
    candidate = candidate or shutil.which(name) or str(Path.home() / "bin" / name)
    path = Path(shutil.which(candidate) or candidate).absolute()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise FileNotFoundError(f"Set {variable} to the {name} executable")
    return path


def installation():
    return Path(os.environ.get("MPW", str(Path.home() / "mpw"))).resolve()


def c_libraries():
    root = installation()
    return [Path(name.replace("{Libraries}", str(root / "Libraries/Libraries") + "/")
                     .replace("{CLibraries}", str(root / "Libraries/CLibraries") + "/"))
            for name in C_LIBRARIES]


def c_tool_commands(name, libraries):
    return (["SC", name + ".c", "-o", name + ".c.o", "-w", "iserror"],
            ["Link", "-c", "MPS ", "-t", "MPST", "-o", name, name + ".c.o", *map(str, libraries)])


def write_changed(path, data, text=False):
    path = Path(path)
    changed = not path.exists() or path.read_bytes() != data
    if changed:
        path.write_bytes(data)
    if text:
        finder_info = b"TEXTMPS " + bytes(24)
        if hasattr(os, "setxattr"):
            os.setxattr(path, "com.apple.FinderInfo", finder_info)
        else:
            subprocess.run(["/usr/bin/xattr", "-wx", "com.apple.FinderInfo", finder_info.hex(), str(path)],
                           check=True, capture_output=True)
    return changed


def run(runner, tool, arguments, build):
    command = [runner, tool, *map(str, arguments)]
    result = subprocess.run(command, cwd=build, capture_output=True)
    stdout = result.stdout.decode("mac_roman").replace("\r", "\n")
    stderr = result.stderr.decode("mac_roman").replace("\r", "\n")
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command, stdout, stderr)
    return stdout, stderr


def stage(path, assembly):
    write_changed(path, assembly.replace("\n", "\r").encode("mac_roman"), text=True)


def build_tool(name, build):
    build = Path(build).resolve()
    build.mkdir(parents=True, exist_ok=True)
    runner = executable()
    stage(build / (name + ".c"), (TOOLS / (name + ".c")).read_text())
    commands = c_tool_commands(name, c_libraries())
    for command in commands:
        run(runner, command[0], command[1:], build)
    return {"executable": build / name, "runner": [str(runner)], "directory": str(build),
            "compile_command": [str(runner), *commands[0]], "link_command": [str(runner), *commands[1]]}


def resource_data(path):
    data = (Path(path) / "..namedfork/rsrc").read_bytes()
    if len(data) < 16:
        raise ValueError("Truncated MPW resource fork")
    offset, map_offset, length, map_length = struct.unpack_from(">4I", data)
    if offset + length > len(data) or map_offset + map_length > len(data) or map_length < 28:
        raise ValueError("Invalid MPW resource fork bounds")
    types = map_offset + struct.unpack_from(">H", data, map_offset + 24)[0]
    if types + 10 > map_offset + map_length:
        raise ValueError("Invalid MPW resource type list")
    if struct.unpack_from(">H", data, types)[0] != 0 or data[types + 2:types + 6] != b"ROM ":
        raise ValueError("MPW Link must emit only one ROM resource")
    count, reference = struct.unpack_from(">HH", data, types + 6)
    reference += types
    if count != 0 or reference + 12 > map_offset + map_length:
        raise ValueError("Invalid MPW ROM reference list")
    identifier = struct.unpack_from(">h", data, reference)[0]
    resource_offset = int.from_bytes(data[reference + 5:reference + 8], "big")
    if identifier != 0 or resource_offset != 0 or length < 4:
        raise ValueError("Unexpected MPW ROM resource")
    size = struct.unpack_from(">I", data, offset)[0]
    if size + 4 != length:
        raise ValueError("Unexpected data outside the MPW ROM resource")
    return data[offset + 4:offset + 4 + size]


def listing_symbols(path):
    text = Path(path).read_bytes().decode("mac_roman").replace("\r", "\n")
    symbols = {}
    size = None
    for line in text.splitlines():
        match = re.match(r"^([0-9A-Fa-f]{5,8})[^\t]*\t(.*)$", line)
        if not match:
            continue
        position, statement = int(match[1], 16), match[2].strip()
        label = re.fullmatch(r"(\w+)\s+(?:EQU\s+\*|PROC(?:\s+EXPORT)?)(?:\s*)", statement, re.I)
        if label:
            symbols[label[1].lower()] = position
        equate = re.fullmatch(r"(\w+)\s+EQU\s+(.+)", statement, re.I)
        if equate:
            value = re.match(r"^[0-9A-Fa-f]{5,8}\s+([0-9A-Fa-f]{4}) ([0-9A-Fa-f]{4})\s", line)
            if value:
                number = int(value[1] + value[2], 16)
                symbols[equate[1].lower()] = number if number < 0x80000000 else number - 0x100000000
        if statement.upper() == "ENDP":
            size = position
    if size is None:
        raise ValueError(f"Missing MPW module end in {path}")
    return symbols, size


def link_map(path):
    text = Path(path).read_bytes().decode("mac_roman").replace("\r", "\n")
    return {match[1].lower(): int(match[2], 16) for match in re.finditer(
        r"^(\w+)\s+\S+\s+\$[0-9A-Fa-f]+,\$([0-9A-Fa-f]+)\b", text, re.M)}


def assemble(assembly, name, runner, build):
    build = Path(build).resolve() / "modules" / name
    build.mkdir(parents=True, exist_ok=True)
    stage(build / (name + ".a"), assembly)
    output, diagnostics = run(runner, "Asm", ["-sym", "on,nolines", "-wb", "-l",
                             "-o", name + ".o", name + ".a"], build)
    (build / (name + ".assembler.txt")).write_text(output + diagnostics)
    listing, diagnostics = run(runner, "Link", ["-t", "ZROM", "-rt", "ROM =0", "-l",
                              "-o", name + ".rom", name + ".o"], build)
    (build / (name + ".map")).write_text(listing)
    if diagnostics.strip():
        raise ValueError(f"MPW Link diagnostics: {diagnostics}")
    symbols, size = listing_symbols(build / (name + ".a.lst"))
    binary = resource_data(build / (name + ".rom"))
    if len(binary) != size:
        raise ValueError("MPW Link changed the assembled module length")
    return binary, symbols
