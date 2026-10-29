#!/usr/bin/env python3
"""Feed the real ROM header to FUN 0x72170 and capture the DER public key."""
import hashlib
import sys

from emu import Emu

BLOB_ADDR = 0x50001000


class Capture(Emu):
    def __init__(self, path):
        super().__init__(path)
        self.bio = None

    def _sha(self, name, sizes):
        def h(uc, data, n, md, r3):
            if md:
                self.wr(md, hashlib.new(name.lower(), self.rd(data, n)).digest()[: sizes[name]])
            return md

        return h

    def _imp_SHA1(self, uc, d, n, md, r3):
        return self._sha("SHA1", {"SHA1": 20})(uc, d, n, md, r3)

    def _imp_SHA256(self, uc, d, n, md, r3):
        return self._sha("SHA256", {"SHA256": 32})(uc, d, n, md, r3)

    def _imp_SHA512(self, uc, d, n, md, r3):
        return self._sha("SHA512", {"SHA512": 64})(uc, d, n, md, r3)

    def _imp_BIO_new_mem_buf(self, uc, buf, n, r2, r3):
        self.bio = (buf, n)
        return 0x1000

    def _imp_BIO_free(self, uc, bio, r1, r2, r3):
        return 0

    def _imp_d2i_RSA_PUBKEY_bio(self, uc, bio, out, r2, r3):
        return 0x2000

    def _imp_RSA_size(self, uc, rsa, r1, r2, r3):
        return 256


def main():
    rom_path = sys.argv[1]
    rom = open(rom_path, "rb").read()
    blob = rom[0:0x200]
    kind = rom[0x808]
    print("rom size %#x, header[0:4]=%s, kind=%#x" % (len(rom), rom[:4].hex(), kind))
    e = Capture("version.elf")
    e.map_region(0x50000000, 0x10000)
    e.wr(BLOB_ADDR, blob)
    ret = e.call(0x72170, [BLOB_ADDR, 0x200, kind])
    print("r0 = %#x" % ret)
    if not e.bio:
        print("no BIO captured")
        return
    buf, n = e.bio
    der = bytes(e.rd(buf, n))
    print("DER len %d, first 8: %s" % (n, der[:8].hex()))
    ok = der[:4] == bytes.fromhex("30820222")
    print("prefix 30 82 02 22:", ok)
    open("/tmp/pubkey.der", "wb").write(der)
    print("sha256:", hashlib.sha256(der).hexdigest())


if __name__ == "__main__":
    main()
