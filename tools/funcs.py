#!/usr/bin/env python3
"""Tiny ARM function map: enumerate 'bl' targets, find enclosing function, list callers.

Usage:
  python3 funcs.py FILE                      # top-level summary
  python3 funcs.py FILE enclosing 0x711a8    # start of function containing addr
  python3 funcs.py FILE callers 0x71000      # who calls this function start
  python3 funcs.py FILE listing 0x71000 0x71200
"""
import struct
import sys

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM


def load(path):
    data = open(path, "rb").read()
    phoff = struct.unpack_from("<I", data, 28)[0]
    phentsize = struct.unpack_from("<H", data, 42)[0]
    phnum = struct.unpack_from("<H", data, 44)[0]
    segs = []
    for i in range(phnum):
        o = phoff + i * phentsize
        p_type, p_offset, p_vaddr, _pp, p_filesz, p_memsz = struct.unpack_from(
            "<IIIIII", data, o
        )
        if p_type == 1:
            segs.append((p_vaddr, p_offset, p_filesz, p_memsz))
    return data, segs


def seg_for(segs, addr):
    for v, o, fs, _ms in segs:
        if v <= addr < v + fs:
            return v, o, fs
    return None


def build_calls(data, segs):
    """Disassemble the executable LOAD segment, return (bl_edges, starts)."""
    ex = max(segs, key=lambda s: s[2] if s[0] < 0x100000 else 0)
    base, off, size, _mem = ex
    code = data[off : off + size]
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    md.detail = False
    edges = []  # (from_addr, to_addr)
    for insn in md.disasm(code, base):
        if insn.mnemonic == "bl":
            try:
                tgt = int(insn.op_str, 0)
            except ValueError:
                continue
            edges.append((insn.address, tgt))
    return edges


def main():
    path = sys.argv[1]
    data, segs = load(path)
    edges = build_calls(data, segs)
    starts = sorted({t for _f, t in edges})
    if len(sys.argv) == 2:
        print("bl edges:", len(edges), "unique targets:", len(starts))
        return
    cmd = sys.argv[2]
    if cmd == "enclosing":
        addr = int(sys.argv[3], 0)
        cand = [s for s in starts if s <= addr]
        print("enclosing:", hex(cand[-1]) if cand else "none")
    elif cmd == "callers":
        tgt = int(sys.argv[3], 0)
        s = sorted({f for f, t in edges if t == tgt})
        for f in s:
            enc = [x for x in starts if x <= f]
            print("call site %08x in function %s" % (f, hex(enc[-1]) if enc else "?"))
    elif cmd == "listing":
        a, b = int(sys.argv[3], 0), int(sys.argv[4], 0)
        v, o, fs = seg_for(segs, a)
        md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        for insn in md.disasm(data[o + a - v : o + b - v], a):
            print("%08x:  %-7s %s" % (insn.address, insn.mnemonic, insn.op_str))
    else:
        print("unknown command", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
