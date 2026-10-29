#!/usr/bin/env python3
"""Test candidate key blobs against the key builder FUN 0x72170."""
import hashlib
import sys

from emu import Emu

BLOB_ADDR = 0x50001000


class Capture(Emu):
    def __init__(self, path):
        super().__init__(path)
        self.bio = None

    def _sha(self, name, size):
        def h(uc, data, n, md, r3):
            if md:
                self.wr(md, hashlib.new(name.lower(), self.rd(data, n)).digest()[:size])
            return md

        return h

    def _imp_SHA1(self, uc, d, n, md, r3):
        return self._sha("SHA1", 20)(uc, d, n, md, r3)

    def _imp_SHA256(self, uc, d, n, md, r3):
        return self._sha("SHA256", 32)(uc, d, n, md, r3)

    def _imp_SHA512(self, uc, d, n, md, r3):
        return self._sha("SHA512", 64)(uc, d, n, md, r3)

    def _imp_BIO_new_mem_buf(self, uc, buf, n, r2, r3):
        self.bio = (buf, n)
        return 0x1000

    def _imp_BIO_free(self, uc, bio, r1, r2, r3):
        return 0

    def _imp_d2i_RSA_PUBKEY_bio(self, uc, bio, out, r2, r3):
        return 0x2000

    def _imp_RSA_size(self, uc, rsa, r1, r2, r3):
        return 256


def try_blob(blob, kind, label):
    e = Capture("version.elf")
    e.map_region(0x50000000, 0x10000)
    e.wr(BLOB_ADDR, blob)
    e.call(0x72170, [BLOB_ADDR, 0x200, kind])
    if not e.bio:
        print("%-22s kind=%3d: no BIO" % (label, kind))
        return None
    buf, n = e.bio
    der = bytes(e.rd(buf, n))
    ok = der[:4] == bytes.fromhex("30820222")
    print("%-22s kind=%3d: len=%d first8=%s der=%s" % (label, kind, n, der[:8].hex(), ok))
    return der if ok else None


def main():
    data = open("version.elf", "rb").read()
    for off in (0xF10, 0x59460, 0x0):
        blob = data[off : off + 0x200]
        for kind in (0, 1, 2):
            der = try_blob(blob, kind, "file+%#x" % off)
            if der:
                open("/tmp/pubkey.der", "wb").write(der)
                print("saved /tmp/pubkey.der")
                return


if __name__ == "__main__":
    main()
