#!/usr/bin/env python3
"""Minimal ARM/Thumb disassembler for ELF32 little-endian PIE.

Usage: python3 disasm.py FILE START END [thumb|arm]
"""
import struct
import sys

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM


def load(path):
    data = open(path, "rb").read()
    assert data[:4] == b"\x7fELF", "not ELF"
    phoff = struct.unpack_from("<I", data, 28)[0]
    phentsize = struct.unpack_from("<H", data, 42)[0]
    phnum = struct.unpack_from("<H", data, 44)[0]
    entry = struct.unpack_from("<I", data, 24)[0]
    segs = []
    for i in range(phnum):
        o = phoff + i * phentsize
        p_type, p_offset, p_vaddr, _p_paddr, p_filesz, p_memsz = struct.unpack_from(
            "<IIIIII", data, o
        )
        if p_type == 1:  # PT_LOAD
            segs.append((p_vaddr, p_offset, p_filesz, p_memsz))
    return data, segs, entry


def read(segs, data, addr, n):
    for v, o, fs, _ms in segs:
        if v <= addr < v + fs:
            return data[o + addr - v : o + addr - v + n]
    return b""


def main():
    path = sys.argv[1]
    start = int(sys.argv[2], 0)
    end = int(sys.argv[3], 0)
    mode = sys.argv[4] if len(sys.argv) > 4 else None
    data, segs, entry = load(path)
    if mode is None:
        mode = "thumb" if entry & 1 else "arm"
    cs_mode = CS_MODE_THUMB if mode == "thumb" else CS_MODE_ARM
    md = Cs(CS_ARCH_ARM, cs_mode)
    md.detail = False
    code = read(segs, data, start & ~1, end - start)
    if not code:
        print("no bytes at that range", file=sys.stderr)
        return 1
    for insn in md.disasm(code, start & ~1):
        print("%08x:  %-7s %s" % (insn.address, insn.mnemonic, insn.op_str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
