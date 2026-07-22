#!/usr/bin/env python3
"""Splice freshly-compiled SPIR-V into shaders_embedded.hpp byte arrays.

Usage: splice_spv.py <hpp> <idx>=<file.spv> [<idx>=<file.spv> ...]
Replaces the body of `shader_<idx>_data[] = { ... };` in place, preserving the
existing 12-bytes-per-line / 4-space-indent formatting and LF line endings.
"""
import re
import sys


def carray(data):
    lines = []
    for i in range(0, len(data), 12):
        chunk = data[i:i + 12]
        lines.append("    " + ", ".join("0x%02x" % b for b in chunk) + ",")
    return "\n".join(lines)


def main():
    hpp = sys.argv[1]
    with open(hpp, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    if "\r\n" in text:
        sys.exit("refusing to edit: file has CRLF line endings")

    for arg in sys.argv[2:]:
        idx, path = arg.split("=", 1)
        with open(path, "rb") as f:
            data = f.read()
        if len(data) < 4 or data[:4] != b"\x03\x02\x23\x07":
            sys.exit("%s: not little-endian SPIR-V (bad magic)" % path)

        head = "inline constexpr std::uint8_t shader_%s_data[] = {\n" % idx
        start = text.find(head)
        if start < 0:
            sys.exit("array shader_%s_data not found" % idx)
        body_start = start + len(head)
        end = text.find("};\n", body_start)
        if end < 0:
            sys.exit("unterminated array shader_%s_data" % idx)

        old_bytes = len(re.findall(r"0x[0-9a-fA-F]{2}", text[body_start:end]))
        text = text[:body_start] + carray(data) + "\n" + text[end:]
        print("shader_%s_data: %d -> %d bytes (%s)" % (idx, old_bytes, len(data), path))

    with open(hpp, "w", encoding="utf-8", newline="") as f:
        f.write(text)


main()
