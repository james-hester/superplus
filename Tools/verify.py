#!/usr/bin/env python3
import argparse
import ast
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


from paths import HERE, HISTORICAL_ROOT, source_path, historical_path, inventory_record

ROOT = HERE
IGNORED = {"BLANKS", "STRING", "ENDP", "ENDPROC"}
SCOPE = {"PROC", "FUNC"}
IDENTIFIER = re.compile(r"(?<![\w.])(@[A-Za-z0-9_]+)")
INCLUDE = re.compile(r"\s+INCLUDE\s+'([^']+)'\s*(?:;.*)?", re.I)
SHARED_INCLUDES = HERE / "Source" / "Includes"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class AssemblyText(str):
    def __new__(cls, text, dependencies):
        result = super().__new__(cls, text)
        result.dependencies = dependencies
        result.adjacency = None
        return result


def expand_includes(source, dependencies, stack=(), include_dirs=None):
    if include_dirs is None:
        include_dirs = (SHARED_INCLUDES,)
    source = source.resolve()
    if source in stack:
        raise ValueError(f"Include cycle: {' -> '.join(map(str, (*stack, source)))}")
    content = source.read_bytes()
    digest = sha256(content)
    if str(source) in dependencies and dependencies[str(source)] != digest:
        raise ValueError(f"Source changed during translation: {source}")
    dependencies[str(source)] = digest
    lines = []
    for number, line in enumerate(content.decode("utf-8").splitlines(), 1):
        match = INCLUDE.fullmatch(line)
        if match:
            if Path(match[1]).name != match[1] or ":" in match[1] or "\\" in match[1]:
                raise ValueError(f"{source}:{number}: include must name a file in the same directory or include path")
            candidates = [directory / match[1] for directory in (source.parent, *include_dirs)]
            child = next((path for path in candidates if path.is_file()), None)
            if child is None:
                raise FileNotFoundError(f"{source}:{number}: include not found: {match[1]}")
            lines.append(expand_includes(child, dependencies, (*stack, source), include_dirs))
        elif re.match(r"\s+INCLUDE\b", line, re.I):
            raise ValueError(f"{source}:{number}: unsupported INCLUDE syntax")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def expression(value, scope):
    value = re.sub(r"'([^']*)'", lambda m: str(int.from_bytes(m[1].encode("mac_roman"), "big")), value)
    value = re.sub(r"(^|[(,+\-/&|^#])\s*\*", r"\1.", value)
    value = re.sub(r"\$([0-9a-fA-F]+)", r"0x\1", value)
    value = re.sub(r"(?<![\w.])0[0-9]+(?![\w.])", lambda m: str(int(m[0])), value)
    value = IDENTIFIER.sub(lambda m: scope + "__local_" + m[1][1:], value)
    return value.lower()


def data_expression(value, scope, byte_strings=False):
    item_pattern = r"(?:'(?:[^']|'')*'|[^,'])+"
    if not re.fullmatch(item_pattern + "(?:," + item_pattern + ")*", value):
        raise ValueError(f"Unsupported data operands: {value}")
    items = re.findall(item_pattern, value)
    values = []
    for item in items:
        literal = re.fullmatch(r"\s*'((?:[^']|'')*)'\s*", item)
        if byte_strings and literal:
            values.extend(str(b) for b in literal[1].replace("''", "'").encode("mac_roman"))
        else:
            values.append(expression(item, scope))
    return ", ".join(values)


def strip_comment(line):
    if line.startswith("*"):
        return ""
    quoted = False
    for index, char in enumerate(line):
        if char == "'":
            quoted = not quoted
        elif char == ";" and not quoted:
            return line[:index]
    return line


def parse_line(line):
    code = strip_comment(line).rstrip()
    label = None
    if code and not code[0].isspace():
        parts = code.split(None, 1)
        label = parts[0].rstrip(":")
        code = parts[1] if len(parts) == 2 else ""
    parts = code.split(None, 1)
    return label, parts[0].upper() if parts else "", parts[1] if len(parts) == 2 else ""


def integer_expression(value, constants):
    value = re.sub(r"&Eval\(", "(", value, flags=re.I)
    tree = ast.parse(expression(value, "module"), mode="eval")
    operations = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
                  ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a // b,
                  ast.FloorDiv: lambda a, b: a // b, ast.LShift: lambda a, b: a << b,
                  ast.RShift: lambda a, b: a >> b, ast.BitOr: lambda a, b: a | b,
                  ast.BitAnd: lambda a, b: a & b, ast.BitXor: lambda a, b: a ^ b}

    def visit(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            return constants[node.id.lower()]
        if isinstance(node, ast.UnaryOp):
            n = visit(node.operand)
            if isinstance(node.op, ast.USub): return -n
            if isinstance(node.op, ast.UAdd): return n
            if isinstance(node.op, ast.Invert): return ~n
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](visit(node.left), visit(node.right))
        raise ValueError(f"Unsupported integer expression: {value}")

    return visit(tree.body)


def expand_macros(lines):
    lines = [line for line in lines if not line.startswith("*")]
    definitions = {}
    globals_ = {}
    constants = {}
    procedure = None

    def condition_value(text):
        match = re.fullmatch(r"(.+?)\s*(<>|<=|>=|=|<|>)\s*(.+?)", text)
        if not match:
            return bool(integer_expression(text, constants))
        left, op, right = match.groups()
        a, b = integer_expression(left, constants), integer_expression(right, constants)
        return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b,
                "<=": a <= b, ">=": a >= b}[op]

    def expand_sequence(lines, depth=0, arguments=None, parameter_names=()):
        nonlocal procedure, constants
        if depth > 32:
            raise ValueError("Macro expansion exceeds 32 levels")
        active = [True]
        taken = []
        saw_else = []
        result = []
        iterator = iter(lines)
        for line in iterator:
            if arguments is not None:
                bindings = {name: arguments[i] if i < len(arguments) else ""
                            for i, name in enumerate(parameter_names)}
                line = re.sub(r"&([A-Za-z_][A-Za-z0-9_]*)",
                              lambda m: bindings.get(m[1].lower(), m[0]), line)
                line = re.sub(r"&Sysl(?:i)?st\[(\d+)\]",
                              lambda m: arguments[int(m[1]) - 1], line, flags=re.I)
                line = re.sub(r"&Eval\(([^()]*)\)", r"(\1)", line, flags=re.I)
            code = strip_comment(line).strip()
            if code.startswith(".*"):
                continue
            if code.upper() == "MACRO":
                declaration = strip_comment(next(iterator, "")).strip().lower()
                match = re.fullmatch(r"([a-z_][a-z0-9_]*)(?:\s+(.+))?", declaration)
                if not match:
                    raise ValueError(f"Unsupported macro name: {declaration}")
                name, parameters = match.groups()
                parameter_names_ = []
                if parameters:
                    for parameter in parameters.split(","):
                        parameter = parameter.strip()
                        if not re.fullmatch(r"&[a-z_][a-z0-9_]*", parameter):
                            raise ValueError(f"Unsupported macro parameter: {parameter}")
                        if parameter[1:] in parameter_names_:
                            raise ValueError(f"Duplicate macro parameter: {parameter}")
                        parameter_names_.append(parameter[1:])
                body = []
                for body_line in iterator:
                    if strip_comment(body_line).strip().upper() == "ENDM":
                        break
                    body.append(body_line)
                else:
                    raise ValueError(f"Unterminated macro: {name}")
                if active[-1]:
                    definitions[name] = (body, parameter_names_)
                continue
            condition = re.fullmatch(r"(IF|ELSEIF)\s+(.+?)\s+THEN", code, re.I)
            if condition:
                if condition[1].upper() == "IF":
                    selected = active[-1] and condition_value(condition[2])
                    active.append(selected)
                    taken.append(selected)
                    saw_else.append(False)
                else:
                    if len(active) == 1 or saw_else[-1]:
                        raise ValueError("Unmatched ELSEIF or ELSEIF after ELSE")
                    selected = active[-2] and not taken[-1] and condition_value(condition[2])
                    active[-1] = selected
                    taken[-1] |= selected
            elif code.upper() == "ELSE":
                if len(active) == 1 or saw_else[-1]:
                    raise ValueError("Unmatched or repeated ELSE")
                active[-1] = active[-2] and not taken[-1]
                taken[-1] = True
                saw_else[-1] = True
            elif code.upper() == "ENDIF":
                if len(active) == 1:
                    raise ValueError("Unmatched ENDIF")
                active.pop()
                taken.pop()
                saw_else.pop()
            elif re.match(r"(?:IF|ELSEIF|ELSE|ENDIF)\b", code, re.I):
                raise ValueError(f"Unsupported condition: {code}")
            elif active[-1]:
                label, op, operands = parse_line(line)
                if op in SCOPE:
                    procedure = label
                    constants = dict(globals_)
                if op == "EQU":
                    try:
                        constants[label.lower()] = integer_expression(operands, constants)
                        if procedure is None:
                            globals_[label.lower()] = constants[label.lower()]
                    except (KeyError, SyntaxError):
                        pass
                if op.lower() in definitions:
                    if label:
                        result.append(label)
                    args = [a.strip() for a in operands.split(",")] if operands else []
                    macro_body, names = definitions[op.lower()]
                    if names and len(args) > len(names):
                        raise ValueError(f"Too many arguments for macro {op}")
                    result.extend(expand_sequence(macro_body, depth + 1, args, names))
                else:
                    result.append(line)
        if len(active) != 1:
            raise ValueError("Unterminated condition")
        return result

    return expand_sequence(lines)


def prepare_mpw(lines):
    body, pending = [], []
    for line in lines:
        label, op, value = parse_line(line)
        if op == "EQU":
            value = re.sub(r"(?<![\w.])\.(?![\w.])", "*", value)
            line = f"{label} EQU {value}"
            if not re.match(r"\s*\*(?:\s*[+\-]|\s*$)", value):
                pending.append((label, value))
                continue
        body.append(line)
    constants = {}
    while pending:
        rest = []
        for label, value in pending:
            try:
                number = integer_expression(value, constants)
            except (KeyError, SyntaxError, ValueError):
                rest.append((label, value))
            else:
                if label in constants and constants[label] != number:
                    raise ValueError(f"Conflicting equate: {label}")
                constants[label] = number
        if len(rest) == len(pending):
            break
        pending = rest
    labels = {parse_line(line)[0].lower() for line in body if parse_line(line)[0]}
    imports = {name.strip().lower() for line in body
               if parse_line(line)[1] == "IMPORT" for name in parse_line(line)[2].split(",")}
    known = labels | set(constants) | imports
    tail = []
    while pending:
        rest = []
        for label, value in pending:
            identifiers = set(re.findall(r"(?<![\w.])[a-z_]\w*", value))
            if identifiers <= known:
                tail.append(f"{label} EQU {value}")
                known.add(label)
            else:
                rest.append((label, value))
        if len(rest) == len(pending):
            raise ValueError(f"Unresolved equates: {rest}")
        pending = rest
    aliases = dict((parse_line(line)[0], parse_line(line)[2]) for line in tail)
    output = ["\tMACHINE MC68000", "\tOPT SYNON"]
    output.extend(f"{label} EQU {number}" for label, number in constants.items())
    checks = []
    for line in body:
        label, op, operands = parse_line(line)
        if op in {"DC.B", "DC.W", "DC.L"}:
            values = operands.split(", ")
            output.extend(f"\t{op} " + ",".join(values[i:i + 20]) for i in range(0, len(values), 20))
            continue
        if op.startswith("MOVEM"):
            operands = re.sub(r"d([0-7])-a([0-7])", r"d\1-d7/a0-a\2", operands)
            line = f"\t{op} {operands}"
        if op == "MOVE.L" and (match := re.fullmatch(r"#(.+),d([0-7])", operands)):
            try:
                number = integer_expression(match[1], constants)
            except (KeyError, SyntaxError, ValueError):
                number = None
            if number is not None and -128 <= number <= 127:
                line = f"\tMOVEQ #{number},d{match[2]}"
        if op == "MOVEQ":
            match = re.fullmatch(r"#(.+),d([0-7])", operands)
            if match:
                try:
                    integer_expression(match[1], constants)
                except (KeyError, SyntaxError, ValueError):
                    value = match[1]
                    for _ in range(len(aliases)):
                        expanded = re.sub(r"(?<![\w.])([a-z_]\w*)", lambda m:
                                          "(" + aliases[m[1]] + ")" if m[1] in aliases else m[1], value)
                        if expanded == value:
                            break
                        value = expanded
                    output.append(f"\tDC.W ${0x7000 + int(match[2]) * 512:04x}+(({value}) AND $ff)")
                    checks.append(match[1])
                    continue
        address_immediate = re.fullmatch(r"(ADD|SUB|CMP|MOVE)A?\.L", op)
        if address_immediate and re.fullmatch(r"#[^,]+,(a[0-7]|sp)", operands):
            output.extend(["\tOPT NONE", f"\t{address_immediate[1]}A.L {operands}", "\tOPT SYNON"])
        elif re.fullmatch(r"(?:ADD|SUB)(?:\.[BWL])?", op) and operands.startswith("#"):
            amount, destination = operands[1:].split(",", 1)
            try:
                number = integer_expression(amount, constants)
            except (KeyError, SyntaxError, ValueError):
                number = None
            if number is not None and 1 <= number <= 8:
                mnemonic, _, width = op.partition(".")
                line = f"\t{mnemonic}Q.{width or 'W'} #{number},{destination}"
            output.append(line)
        elif re.fullmatch(r"B(?:RA|SR|HI|LS|CC|HS|CS|LO|NE|EQ|VC|VS|PL|MI|GE|LT|GT|LE)(?:\.[SW])?", op):
            op = op.replace("BHS", "BCC").replace("BLO", "BCS")
            output.extend(["\tOPT NONE", f"\t{op} {operands}", "\tOPT SYNON"])
        else:
            output.append(line)
    output.extend(tail)
    for value in checks:
        for comparison in (f"({value}) < -128", f"({value}) > 127"):
            output.extend([f"\tIF {comparison} THEN", "\tFAIL 'MOVEQ immediate out of range'", "\tENDIF"])
    output.extend(["\tENDP", "\tEND"])
    text = "\n".join(output) + "\n"
    text = re.sub(r"0x([0-9a-fA-F]+)", r"$\1", text)
    text = re.sub(r"(?<![\w$])([0-9]{10,})(?!\w)", lambda m: "$" + format(int(m[1]), "x"), text)
    return text


def translate(source, module_name="ROMModule"):
    dependencies = {}
    text = expand_includes(source, dependencies)
    lines = expand_macros(text.splitlines())
    exports = {name.strip().lower() for line in lines
               if parse_line(line)[1] == "EXPORT" for name in parse_line(line)[2].split(",")}
    exports.update(label.lower() for line in lines for label, op, operands in [parse_line(line)]
                   if label and op in SCOPE and operands.strip().upper() == "EXPORT")
    definitions = {}
    local_equates = {}
    procedure = "module"
    for line in lines:
        code = strip_comment(line)
        label, op, operands = parse_line(line)
        if op in SCOPE and label:
            procedure = label.lower()
        elif op == "EQU" and label and procedure != "module" and label.lower() not in exports:
            local_equates.setdefault(procedure, set()).add(label.lower())
        if code and not code[0].isspace():
            parts = code.split()
            if parts and not (len(parts) > 1 and parts[1].upper() in {"EQU", "OPWORD"}):
                name = parts[0].lower().rstrip(":")
                definitions[name] = definitions.get(name, 0) + 1
    duplicate_labels = {name for name, count in definitions.items()
                        if (count > 1 or name in {"ac", "bc", "control", "status"}) and not name.startswith("@")}
    output = [f"{module_name} PROC EXPORT"]
    scope = "module"
    procedure = "module"
    traps = set()
    imported = set()
    exported = set()
    ended = False
    for number, line in enumerate(lines, 1):
        code = strip_comment(line).rstrip()
        if not code.strip():
            continue
        if ended:
            raise ValueError(f"{source}:{number}: substantive content follows END")
        label = None
        if not code[0].isspace():
            parts = code.split(None, 1)
            label = parts[0].rstrip(":")
            code = parts[1] if len(parts) == 2 else ""
        parts = code.split(None, 1)
        op = parts[0].upper() if parts else ""
        operands = parts[1] if len(parts) == 2 else ""
        if op in SCOPE and label:
            procedure = label.lower()
        names = local_equates.get(procedure, set())
        for name in sorted(names, key=len, reverse=True):
            operands = re.sub(r"\b" + re.escape(name) + r"\b", procedure + "__" + name, operands, flags=re.I)
        if op == "END":
            ended = True
            continue
        if op in {"IMPORT", "EXPORT"}:
            names = [name.strip().lower() for name in operands.split(",")]
            if op == "IMPORT":
                names = [name for name in names if name not in definitions and name not in exports
                         and name not in imported]
                imported.update(names)
            else:
                names = [name for name in names if name not in exported]
                exported.update(names)
            if names:
                output.append("\t" + op + " " + ",".join(names))
            continue
        if op in SCOPE and operands.strip().upper() == "EXPORT":
            if label.lower() not in exported:
                output.append("\tEXPORT " + label.lower())
                exported.add(label.lower())
        if op in {"EQU", "OPWORD"}:
            if label is None:
                raise ValueError(f"{source}:{number}: EQU requires a name")
            value = expression(operands, scope)
            qualified = procedure + "__" + label.lower() if label.lower() in names else label.lower()
            output.append(f"{qualified} {op} {value}")
            if op == "OPWORD":
                traps.add(label.upper())
            continue
        if label:
            if not label.startswith("@"):
                scope = label.lower()
            if label.lower() in duplicate_labels:
                label = procedure + "__" + label
            output.append(expression(label, scope) + " EQU *")
        if not op or op in IGNORED or op in SCOPE:
            continue
        if op == "MACHINE":
            machine = operands.upper()
            if machine not in {"MC68000", "MC68020"}:
                raise ValueError(f"{source}:{number}: unsupported machine {operands}")
            output.append("\tMACHINE " + machine)
            continue
        for name in duplicate_labels:
            operands = re.sub(r"\b" + re.escape(name) + r"\b", procedure + "__" + name, operands, flags=re.I)
        if op in traps:
            output.append("\t" + op + " " + expression(operands, scope))
        elif op in {"DC.B", "DC.W", "DC.L"}:
            directive = op
            output.append("\t" + directive + " " + data_expression(operands, scope, op == "DC.B"))
        else:
            if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:\.[BWLSD])?", op):
                raise ValueError(f"{source}:{number}: unsupported operation {op}")
            output.append("\t" + op.lower() + " " + expression(operands, scope))
    return AssemblyText(prepare_mpw(output), dependencies)


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
    """Use adjacent object boundaries for short imports that Asm cannot range-check.

    Asm checks the unresolved byte addend before Link supplies the target.
    The next object's origin and this object's end provide an equivalent
    expression with a small addend. Link still checks the signed byte range;
    verification checks that the two boundaries coincide.
    """
    assemblies = {module["name"]: module_assembly(module) for module in modules
                  if module.get("format") != "rez-data"}
    for module, following in zip(modules, modules[1:]):
        if (module["name"] not in assemblies or following["name"] not in assemblies
                or following.get("format") == "mpw-compressed-dispatch"):
            continue
        assembly = assemblies[module["name"]]
        next_text = assemblies[following["name"]]
        next_exports = {name.strip().lower() for line in next_text.splitlines()
                        if parse_line(line)[1] == "EXPORT" for name in parse_line(line)[2].split(",")}
        imports = {name.strip().lower() for line in assembly.splitlines()
                   if parse_line(line)[1] == "IMPORT" for name in parse_line(line)[2].split(",")}
        next_name = "rom_" + following["name"].replace("-", "_")
        end_name = "rom_" + module["name"].replace("-", "_") + "_end"
        conditions = "RA SR HI LS CC CS NE EQ VC VS PL MI GE LT GT LE".split()
        rewritten = []
        count = 0
        for line in assembly.splitlines():
            label, op, operand = parse_line(line)
            if op.endswith(".S") and op[1:-2] in conditions and operand in imports & next_exports:
                opcode = 0x60 + conditions.index(op[1:-2])
                rewritten.append(f"\tDC.B ${opcode:x},{operand}-{next_name}+{end_name}-(*+2)")
                count += 1
            else:
                rewritten.append(line)
        if count:
            for index, line in enumerate(rewritten):
                if parse_line(line)[1] == "PROC":
                    rewritten[index + 1:index + 1] = [f"\tIMPORT {next_name}", f"\tEXPORT {end_name}"]
                    break
            end = next(index for index, line in enumerate(rewritten) if parse_line(line)[1] == "ENDP")
            rewritten.insert(end, f"{end_name} EQU *")
            prepared = AssemblyText("\n".join(rewritten) + "\n", getattr(assembly, "dependencies", {}))
            prepared.adjacency = (end_name, next_name)
            assemblies[module["name"]] = prepared
    return assemblies


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
    dependencies = getattr(translated, "dependencies", {})
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
        for assembly in translated.values():
            adjacency = getattr(assembly, "adjacency", None)
            if adjacency and (locations.get(adjacency[0]) is None
                              or locations.get(adjacency[0]) != locations.get(adjacency[1])):
                raise ValueError(f"MPW Link separated adjacent short-branch modules: {adjacency}")
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
            offsets, size = mpw.listing_symbols(args.build / (name + ".a.lst"))
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
