from pathlib import Path
import struct
import subprocess

from stage import ROOT, stage, write_text


def build_tool(name, build):
    build = Path(build).resolve()
    stage(build)
    subprocess.run(["make", "-f", str(ROOT / "Makefile"), "native",
                    "BUILD=" + str(build), "TARGET=" + name],
                   cwd=build, check=True, capture_output=True)
    return {"executable": build / name, "runner": ["mpw"]}


def assemble(assembly, name, runner, build):
    build = Path(build)
    write_text(build / (name + ".a"), assembly)
    subprocess.run([runner, "Asm", "-o", name + ".o", name + ".a"],
                   cwd=build, check=True, capture_output=True)
    subprocess.run([runner, "Link", "-t", "ZROM", "-rt", "ROM =0", "-o",
                    name + ".rom", name + ".o"], cwd=build, check=True, capture_output=True)
    return resource_data(build / (name + ".rom"))


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
