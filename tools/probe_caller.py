#!/usr/bin/env python3
"""Emulate the top-level verifier FUN 0x6f778 with real file hooks.

Goal: observe the genuine (blob, 0x200, type) passed to FUN 0x72170 and capture
the derived public key plus the RSA-decrypted AES key material.
"""
import hashlib
import sys
import struct

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3

from emu import Emu

ROM_MAP = 0x40000000
ROM_SIZE = 0x4000000
FD_ROM = 3


class Verifier(Emu):
    def __init__(self, path, rom):
        super().__init__(path)
        self.rom = rom
        self.bio = None
        self.captured = None
        self.opens = []
        self.next_fd = 3

    # --- file layer ---
    def _alloc_fd(self):
        fd = self.next_fd
        self.next_fd += 1
        return fd

    def _imp_open(self, uc, path, flags, mode, r3):
        p = self.rdstr(path)
        fd = self._alloc_fd()
        self.opens.append((p, flags, mode, fd))
        print("  open(%r, flags=%#x) -> fd %d" % (p, flags, fd))
        return fd

    def _imp_openat(self, uc, dfd, path, flags, r3):
        return self._imp_open(uc, path, flags, 0, r3)

    def _imp_close(self, uc, fd, r1, r2, r3):
        print("  close(%d)" % fd)
        return 0

    def _imp_lseek(self, uc, fd, off, whence, r3):
        off &= 0xFFFFFFFF
        if off >= 0x80000000:
            off -= 0x100000000
        print("  lseek(%d, %d, %d)" % (fd, off, whence))
        return off & 0xFFFFFFFF

    def _imp_read(self, uc, fd, buf, n, r3):
        for p, flags, mode, fdv in self.opens:
            if fdv == fd and p == "/phone/rom":
                off = 0
                data = self.rom[off : off + n]
                self.wr(buf, data)
                print("  read(rom, %d) -> %d" % (n, len(data)))
                return len(data)
        self.wr(buf, b"\0" * n)
        print("  read(fd=%d, %d) -> zero" % (fd, n))
        return n

    def _imp_mmap(self, uc, addr, length, prot, flags, r3=None):
        fd = self._stack_arg(5)
        off = self._stack_arg(6)
        print("  mmap(addr=%#x, len=%#x, prot=%d, flags=%#x, fd=%d, off=%#x)" % (addr, length, prot, flags, fd, off))
        if fd in [o[3] for o in self.opens if o[0] == "/phone/rom"]:
            self.map_region(ROM_MAP, len(self.rom) + 0x1000)
            self.wr(ROM_MAP, self.rom)
            print("     -> served real ROM at %#x (%d bytes)" % (ROM_MAP, len(self.rom)))
            return ROM_MAP
        self.map_region(0x41000000, max(length, 0x1000) & 0xFFF00000 or 0x100000)
        self.wr(0x41000000, b"\0" * 0x1000)
        return 0x41000000

    def _imp_readlink(self, uc, path, buf, size, r3):
        p = self.rdstr(path)
        fake = "/phone/rom"
        self.wr(buf, fake.encode() + b"\0")
        print("  readlink(%r, %#x, %d) -> %r" % (p, buf, size, fake))
        return len(fake)

    def _imp_write(self, uc, fd, buf, n, r3):
        print("  write(%d, %#x, %d): %s" % (fd, buf, n, self.rd(buf, min(n, 32)).hex()))
        return n

    def _imp_ioctl(self, uc, fd, req, arg, r3):
        print("  ioctl(%d, %#x, %#x)" % (fd, req, arg))
        return 0

    def _imp_dlopen(self, uc, path, flags, r2, r3):
        print("  dlopen(%r, %d)" % (self.rdstr(path) if path else "", flags))
        return 0x5000

    def _imp_dlsym(self, uc, h, name, r2, r3):
        print("  dlsym(%#x, %r)" % (h, self.rdstr(name)))
        return 0

    def _imp_dlclose(self, uc, h, r1, r2, r3):
        print("  dlclose(%#x)" % h)
        return 0

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
        print("  BIO_new_mem_buf(buf=%#x, len=%d)" % (buf, n))
        return 0x1000

    def _imp_BIO_free(self, uc, bio, r1, r2, r3):
        return 0

    def _imp_d2i_RSA_PUBKEY_bio(self, uc, bio, out, r2, r3):
        print("  d2i_RSA_PUBKEY_bio")
        return 0x2000

    def _imp_RSA_size(self, uc, rsa, r1, r2, r3):
        return 256

    def _imp_RSA_public_decrypt(self, uc, flen, from_, to, rsa, pad):
        print("  RSA_public_decrypt(flen=%d, from=%#x, to=%#x, rsa=%#x, pad=%d)" % (flen, from_, to, rsa, pad))
        self.captured = (from_, flen, to)
        self.wr(to, b"\x11" * 0x20 + b"\0" * 0x20)
        return 0x20


def main():
    rom_path = sys.argv[1]
    rom = open(rom_path, "rb").read()
    e = Verifier("version.elf", rom)
    e.map_region(0x50000000, 0x100000)

    def on_key_builder(uc, address, size, user):
        r0, r1, r2, r3 = (uc.reg_read(x) for x in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3))
        print("  >>> FUN 0x72170(blob=%#x, len=%#x, type=%#x)" % (r0, r1, r2))
        try:
            data = bytes(uc.mem_read(r0, 0x200))
            print("      blob[0:32]:", data[:32].hex())
            print("      blob[0x800:0x810] region check skipped")
        except Exception as exc:
            print("      blob unreadable:", exc)

    e.uc.hook_add(UC_HOOK_CODE, on_key_builder, begin=0x72170, end=0x72170)
    ret = e.call(0x6F778, [0, 0])
    print("returns %#x" % ret)
    if e.bio:
        buf, n = e.bio
        der = bytes(e.rd(buf, n))
        print("DER len", n, "first8", der[:8].hex(), "is-der", der[:4] == bytes.fromhex("30820222"))
        open("/tmp/pubkey.der", "wb").write(der)
    print("captured rsa:", e.captured)


if __name__ == "__main__":
    main()
