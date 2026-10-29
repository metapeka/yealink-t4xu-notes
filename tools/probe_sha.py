#!/usr/bin/env python3
"""Characterise the SHA wrappers with import-level tracing."""
import hashlib
import sys

import emu
from emu import Emu

BLOB_ADDR = 0x50001000
OUT_ADDR = 0x50002000


class Traced(Emu):
    def _imp_memcpy(self, uc, dst, src, n, r3):
        print("  memcpy(%#x, %#x, %d)" % (dst, src, n))
        return super()._imp_memcpy(uc, dst, src, n, r3)

    def _imp_memset(self, uc, dst, val, n, r3):
        print("  memset(%#x, %#x, %d)" % (dst, val, n))
        return super()._imp_memset(uc, dst, val, n, r3)

    def _sha(self, name):
        sizes = {"SHA1": 20, "SHA256": 32, "SHA512": 64}

        def h(uc, data, n, md, r3):
            try:
                raw = self.rd(data, min(n, 64))
            except Exception:
                raw = b"<unreadable>"
            print("  %s(data=%#x, len=%d, md=%#x) data[0:16]=%s" % (name, data, n, md, raw[:16].hex()))
            if md:
                self.wr(md, hashlib.new(name.lower(), self.rd(data, n)).digest()[: sizes[name]])
            return md

        return h

    def _imp_SHA1(self, uc, data, n, md, r3):
        return self._sha("SHA1")(uc, data, n, md, r3)

    def _imp_SHA256(self, uc, data, n, md, r3):
        return self._sha("SHA256")(uc, data, n, md, r3)

    def _imp_SHA512(self, uc, data, n, md, r3):
        return self._sha("SHA512")(uc, data, n, md, r3)

    def _imp_BIO_new_mem_buf(self, uc, buf, n, r2, r3):
        print("  BIO_new_mem_buf(buf=%#x, len=%d)" % (buf, n))
        return 0x1000

    def _imp_BIO_free(self, uc, bio, r1, r2, r3):
        print("  BIO_free(%#x)" % bio)
        return 0

    def _imp_d2i_RSA_PUBKEY_bio(self, uc, bio, out, r2, r3):
        print("  d2i_RSA_PUBKEY_bio(%#x)" % bio)
        return 0x2000

    def _imp_RSA_size(self, uc, rsa, r1, r2, r3):
        print("  RSA_size(%#x)" % rsa)
        return 256


def run(fn, blob, out_size=0x400):
    e = Traced("version.elf")
    e.map_region(0x50000000, 0x10000)
    e.wr(BLOB_ADDR, blob)
    e.wr(OUT_ADDR, b"\xCC" * out_size)
    print("=== wrapper %#x" % fn)
    ret = e.call(fn, [BLOB_ADDR, len(blob), OUT_ADDR])
    out = e.rd(OUT_ADDR, out_size)
    print("  r0=%#x" % ret)
    print("  out[0:0x80] =", out[:0x80].hex())
    print("  out[0x80:0xc0] =", out[0x80:0xC0].hex())
    print()
    return out


def main():
    blob = bytes(range(256)) * 2
    for fn in (0x6D820, 0x6DC00, 0x6E0A0):
        run(fn, blob)


if __name__ == "__main__":
    main()
