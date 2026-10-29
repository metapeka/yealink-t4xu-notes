#!/usr/bin/env python3
"""Reproducible Yealink T4xU ROM rebuild.

Usage:
  python3 rebuild.py SRC.rom -o OUT.rom [--version 108.87.0.21]
                              [--replace NAME=PLAINTEXT_FILE ...]

Rules:
- unchanged blocks are copied byte-for-byte;
- a replaced block is re-encrypted per its `cipher` field, padded to 32 bytes,
  and its header length/total/crc are recomputed;
- ROM header `length` = sum of block totals, `header_crc` = zlib CRC32 over 0x80
  bytes with the crc field zeroed;
- trailing bytes (e.g. 512-byte trailer) are preserved verbatim.
"""
import argparse
import hashlib
import struct
import zlib

import rombuild
from romtool import blocks


def set_version(rom_header: bytearray, ver: str) -> None:
    raw = ver.encode() + bytes(1)
    if len(raw) > 16:
        raise SystemExit('version too long')
    rom_header[0x44:0x54] = raw + bytes(16 - len(raw))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--version')
    ap.add_argument('--replace', action='append', default=[], metavar='NAME=FILE')
    a = ap.parse_args()

    src = open(a.src, 'rb').read()
    repl = {}
    for item in a.replace:
        name, path = item.split('=', 1)
        repl[name] = open(path, 'rb').read()

    data = rombuild.build(src, repl)
    if a.version:
        hdr = bytearray(data[:0x80])
        set_version(hdr, a.version)
        struct.pack_into('>I', hdr, 0x08, 0)
        struct.pack_into('>I', hdr, 0x08, zlib.crc32(bytes(hdr)) & 0xffffffff)
        data = bytes(hdr) + data[0x80:]
    open(a.out, 'wb').write(data)

    size = len(data)
    hdr = data[:0x80]
    length = struct.unpack('>I', hdr[0x14:0x18])[0]
    crc = struct.unpack('>I', hdr[0x08:0x0C])[0]
    calc = zlib.crc32(hdr[:8] + bytes(4) + hdr[12:]) & 0xffffffff
    tail = size - 0x80 - length
    print('out      :', a.out)
    print('size     :', size, '(src %d)' % len(src))
    print('version  :', hdr[0x44:0x54].split(bytes(1))[0].decode())
    print('length   : 0x%X  tail %d' % (length, tail))
    print('hdr crc  : %08X %s' % (crc, 'ok' if crc == calc else 'MISMATCH'))
    bl, _ = blocks(data)
    for b in bl:
        h = rombuild.dec(data[b['off']:b['off'] + 0x80])
        bcrc = struct.unpack('>I', h[8:12])[0]
        bcalc = zlib.crc32(h[:8] + bytes(4) + h[12:]) & 0xffffffff
        print('  block %-10s off=0x%X total=0x%X len=0x%X cipher=%d crc %s'
              % (b['name'], b['off'], b['total'], b['length'], b['cipher'],
                 'ok' if bcrc == bcalc else 'MISMATCH'))
    print('sha256   :', hashlib.sha256(data).hexdigest())


if __name__ == '__main__':
    main()
