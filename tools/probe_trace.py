#!/usr/bin/env python3
"""Trace the whole derivation in FUN 0x72170 to a file for reimplementation."""
import hashlib
import sys

from emu import Emu

BLOB_ADDR = 0x50001000
OUT = open("/tmp/derivation_trace.txt", "w")


class Rec(Emu):
    def __init__(self, path):
        super().__init__(path)
        self.events = 0

    def log(self, line):
        self.events += 1
        if self.events <= 40000:
            OUT.write(line + "\n")

    def _imp_memcpy(self, uc, dst, src, n, r3):
        self.log("memcpy %#x %#x %d" % (dst, src, n))
        return super()._imp_memcpy(uc, dst, src, n, r3)

    def _imp_memset(self, uc, dst, val, n, r3):
        self.log("memset %#x %#x %d" % (dst, val, n))
        return super()._imp_memset(uc, dst, val, n, r3)

    def _sha(self, name, size):
        def h(uc, data, n, md, r3):
            raw = self.rd(data, n)
            self.log("%s %#x %d %#x %s" % (name, data, n, md, raw.hex()))
            if md:
                self.wr(md, hashlib.new(name.lower(), raw).digest()[:size])
            return md

        return h

    def _imp_SHA1(self, uc, d, n, md, r3):
        return self._sha("SHA1", 20)(uc, d, n, md, r3)

    def _imp_SHA256(self, uc, d, n, md, r3):
        return self._sha("SHA256", 32)(uc, d, n, md, r3)

    def _imp_SHA512(self, uc, d, n, md, r3):
        return self._sha("SHA512", 64)(uc, d, n, md, r3)

    def _imp_BIO_new_mem_buf(self, uc, buf, n, r2, r3):
        self.log("BIO %#x %d" % (buf, n))
        self.bio = (buf, n)
        return 0x1000

    def _imp_d2i_RSA_PUBKEY_bio(self, uc, bio, out, r2, r3):
        return 0x2000

    def _imp_BIO_free(self, uc, bio, r1, r2, r3):
        return 0

    def _imp_RSA_size(self, uc, rsa, r1, r2, r3):
        return 256


def main():
    blob = bytes((i * 7 + 3) & 0xFF for i in range(0x200))
    e = Rec("version.elf")
    e.map_region(0x50000000, 0x10000)
    e.wr(BLOB_ADDR, blob)
    e.call(0x72170, [BLOB_ADDR, 0x200, 0])
    OUT.close()
    print("events:", e.events)
    if e.bio:
        buf, n = e.bio
        der = bytes(e.rd(buf, n))
        open("/tmp/der_blob.bin", "wb").write(der)
        print("der first8", der[:8].hex())


if __name__ == "__main__":
    main()
