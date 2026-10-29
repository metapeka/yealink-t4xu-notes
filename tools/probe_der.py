#!/usr/bin/env python3
"""Run FUN 0x72170 (public-key builder) on a synthetic blob and dump the result."""
import hashlib
import sys

from emu import Emu

BLOB_ADDR = 0x50001000
OUT_PAGE = 0x50010000


class Traced(Emu):
    def __init__(self, path):
        super().__init__(path)
        self.counts = {}

    def _bump(self, name, detail=""):
        n = self.counts.get(name, 0) + 1
        self.counts[name] = n
        if n <= 6 or n % 32 == 0:
            print("  %s #%d %s" % (name, n, detail))

    def _imp_memcpy(self, uc, dst, src, n, r3):
        self._bump("memcpy", "(%#x, %#x, %d)" % (dst, src, n))
        return super()._imp_memcpy(uc, dst, src, n, r3)

    def _imp_memset(self, uc, dst, val, n, r3):
        self._bump("memset", "(%#x, %#x, %d)" % (dst, val, n))
        return super()._imp_memset(uc, dst, val, n, r3)

    def _sha(self, name):
        sizes = {"SHA1": 20, "SHA256": 32, "SHA512": 64}

        def h(uc, data, n, md, r3):
            self._bump(name, "(data=%#x, len=%d, md=%#x)" % (data, n, md))
            if md:
                self.wr(md, hashlib.new(name.lower(), self.rd(data, n)).digest()[: sizes[name]])
            return md

        return h

    def _imp_SHA1(self, uc, d, n, md, r3):
        return self._sha("SHA1")(uc, d, n, md, r3)

    def _imp_SHA256(self, uc, d, n, md, r3):
        return self._sha("SHA256")(uc, d, n, md, r3)

    def _imp_SHA512(self, uc, d, n, md, r3):
        return self._sha("SHA512")(uc, d, n, md, r3)

    def _imp_BIO_new_mem_buf(self, uc, buf, n, r2, r3):
        print("  BIO_new_mem_buf(buf=%#x, len=%d)" % (buf, n))
        self.last_bio_buf = buf
        self.last_bio_len = n
        return 0x1000

    def _imp_BIO_free(self, uc, bio, r1, r2, r3):
        print("  BIO_free(%#x)" % bio)
        return 0

    def _imp_d2i_RSA_PUBKEY_bio(self, uc, bio, out, r2, r3):
        print("  d2i_RSA_PUBKEY_bio(%#x, %#x)" % (bio, out))
        return 0x2000

    def _imp_RSA_size(self, uc, rsa, r1, r2, r3):
        print("  RSA_size(%#x)" % rsa)
        return 256


def main():
    blob = bytes(range(256)) * 2
    kind = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0
    e = Traced("version.elf")
    e.map_region(0x50000000, 0x20000)
    e.wr(BLOB_ADDR, blob)
    print("kind =", kind)
    ret = e.call(0x72170, [BLOB_ADDR, len(blob), kind])
    print("returns r0 = %#x" % ret)
    print("counts:", e.counts)
    if getattr(e, "last_bio_buf", None):
        buf, ln = e.last_bio_buf, e.last_bio_len
        print("BIO buffer %#x len %d" % (buf, ln))
        try:
            data = e.rd(buf, ln if 0 < ln < 0x1000 else 0x400)
            print("content:", data[:64].hex())
            print("sha256 :", hashlib.sha256(data).hexdigest())
        except Exception as exc:
            print("cannot read:", exc)


if __name__ == "__main__":
    main()
