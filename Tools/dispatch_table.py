from struct import pack, unpack


TOOLBOX_COUNT = 512
OS_COUNT = 256
ENTRY_COUNT = TOOLBOX_COUNT + OS_COUNT


def encode_dispatch_table(data, rom_size):
    if len(data) != ENTRY_COUNT * 4:
        raise ValueError("Dispatch source must contain 512 Toolbox and 256 OS offsets")
    values = unpack(">" + "I" * ENTRY_COUNT, data)
    output = bytearray()
    previous = 0
    for value in values:
        if value == 0:
            output.append(0x80)
            continue
        if value & 1 or value >= rom_size:
            raise ValueError(f"Invalid dispatch ROM offset: {value:#x}")
        delta = value - previous
        if 2 <= delta <= 252:
            output.append(0x80 | (delta // 2))
        elif delta != 0 and -32768 <= delta <= 32766:
            output.extend(pack(">H", (delta // 2) & 0x7fff))
        else:
            output.append(0xff)
            output.extend(pack(">I", value))
        previous = value
    output.extend(b"\0\0")
    if len(output) & 1:
        output.append(0)
    return bytes(output)


def decode_dispatch_table(data, rom_size):
    values = []
    positions = []
    cursor = 0
    previous = 0
    while cursor < len(data):
        position = cursor
        byte = data[cursor]
        cursor += 1
        if byte == 0x80:
            value = 0
        elif byte == 0xff:
            if cursor + 4 > len(data):
                raise ValueError("Truncated absolute dispatch offset")
            value = int.from_bytes(data[cursor:cursor + 4], "big")
            cursor += 4
            if value == 0 or value & 1 or value >= rom_size:
                raise ValueError("Invalid absolute dispatch offset")
            previous = value
        else:
            if byte < 0x80:
                if cursor == len(data):
                    raise ValueError("Truncated word dispatch offset")
                encoded = (byte << 8) | data[cursor]
                cursor += 1
                delta = (encoded << 1) & 0xffff
                if delta >= 0x8000:
                    delta -= 0x10000
            else:
                delta = (byte & 0x7f) * 2
            if delta == 0:
                if len(values) != ENTRY_COUNT:
                    raise ValueError("Dispatch terminator has the wrong entry count")
                padding = b"\0" if cursor & 1 else b""
                if data[cursor:] != padding:
                    raise ValueError("Unexpected bytes after dispatch terminator")
                return pack(">" + "I" * ENTRY_COUNT, *values), positions
            value = previous + delta
            if value <= 0 or value >= rom_size:
                raise ValueError("Relative dispatch offset leaves ROM")
            previous = value
        values.append(value)
        positions.append(position)
        if len(values) > ENTRY_COUNT:
            raise ValueError("Too many dispatch entries")
    raise ValueError("Missing dispatch terminator")
