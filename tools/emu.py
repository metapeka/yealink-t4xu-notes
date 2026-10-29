#!/usr/bin/env python3
"""Unicorn-based runner for the Yealink updater (version.elf, ARM32 PIE).

Loads the ELF at base 0 (LOAD0) and 0x88000 (LOAD1, aligned per p_align), resolves
every dynamic import to a Python handler through a sentinel GOT, and lets the caller
execute an arbitrary function.

Usage:
    python3 emu.py FILE PC [--thumb] [--arg REG=VALUE ...] [--trace ADDR]
"""
import hashlib
import struct
import sys

from unicorn import (
    Uc,
    UC_ARCH_ARM,
    UC_MODE_ARM,
    UC_MODE_THUMB,
    UC_HOOK_CODE,
    UC_HOOK_MEM_UNMAPPED,
)
from unicorn.arm_const import (
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R3,
    UC_ARM_REG_SP,
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
)

STACK_BASE = 0x7F000000
STACK_SIZE = 0x00100000
HEAP_BASE = 0x60000000
HEAP_SIZE = 0x01000000
SENTINEL_BASE = 0x77000000
SENTINEL_SIZE = 0x00010000
GUARD_ADDR = 0x7E000000
RETURN_TRAP = 0x7E001000


class Elf:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        d = self.data
        assert d[:4] == b"\x7fELF"
        (self.entry,) = struct.unpack_from("<I", d, 24)
        phoff = struct.unpack_from("<I", d, 28)[0]
        self.phentsize = struct.unpack_from("<H", d, 42)[0]
        self.phnum = struct.unpack_from("<H", d, 44)[0]
        self.shoff = struct.unpack_from("<I", d, 32)[0]
        self.shentsize = struct.unpack_from("<H", d, 46)[0]
        self.shnum = struct.unpack_from("<H", d, 48)[0]
        self.shstrndx = struct.unpack_from("<H", d, 50)[0]
        self.loads = []
        self.dynamic = None
        for i in range(self.phnum):
            o = phoff + i * self.phentsize
            p_type, p_off, p_vaddr, _pa, p_fsz, p_msz = struct.unpack_from(
                "<IIIIII", d, o
            )
            p_align = struct.unpack_from("<I", d, o + 28)[0]
            if p_type == 1:
                self.loads.append(
                    {
                        "off": p_off,
                        "vaddr": p_vaddr,
                        "filesz": p_fsz,
                        "memsz": p_msz,
                        "align": p_align,
                    }
                )
            elif p_type == 2:
                self.dynamic = (p_off, p_fsz)

    def sections(self):
        out = []
        shstr_off = struct.unpack_from(
            "<I", self.data, self.shoff + self.shstrndx * self.shentsize + 16
        )[0]
        for i in range(self.shnum):
            o = self.shoff + i * self.shentsize
            name, stype, flags, addr, off, size, link = struct.unpack_from(
                "<IIIIIII", self.data, o
            )
            end = self.data.index(b"\0", shstr_off + name)
            nm = self.data[shstr_off + name : end].decode()
            out.append(
                {
                    "name": nm,
                    "type": stype,
                    "addr": addr,
                    "off": off,
                    "size": size,
                    "link": link,
                }
            )
        return out

    def dynsyms(self):
        secs = {s["name"]: s for s in self.sections()}
        ds = secs[".dynsym"]
        dstr = secs[".dynstr"]
        strtab = self.data[dstr["off"] : dstr["off"] + dstr["size"]]
        syms = []
        for i in range(ds["size"] // 16):
            o = ds["off"] + i * 16
            st_name, st_value, st_size, st_info, _oth, st_shndx = struct.unpack_from(
                "<IIIBBH", self.data, o
            )
            end = strtab.index(b"\0", st_name)
            name = strtab[st_name:end].decode()
            syms.append({"name": name, "value": st_value, "shndx": st_shndx})
        return syms

    def relocations(self, secname):
        secs = {s["name"]: s for s in self.sections()}
        sec = secs[secname]
        syms = self.dynsyms()
        out = []
        for i in range(sec["size"] // 8):
            o = sec["off"] + i * 8
            r_offset, r_info = struct.unpack_from("<II", self.data, o)
            rtype = r_info & 0xFF
            symidx = r_info >> 8
            out.append(
                {
                    "offset": r_offset,
                    "type": rtype,
                    "sym": symidx,
                    "name": syms[symidx]["name"] if symidx < len(syms) else "",
                }
            )
        return out


class Emu:
    def __init__(self, path, verbose=False):
        self.elf = Elf(path)
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.verbose = verbose
        self.handlers = {}  # sentinel addr -> (name, fn)
        self.heap_ptr = HEAP_BASE + 0x1000
        self.trace = None
        self.log = []
        self._map_image()
        self._map_runtime()
        self._install_imports()
        self.uc.hook_add(
            UC_HOOK_CODE,
            self._on_sentinel,
            begin=SENTINEL_BASE,
            end=SENTINEL_BASE + SENTINEL_SIZE - 1,
        )
        self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._on_unmapped)

    # ---------- memory ----------
    def _map_image(self):
        for seg in self.elf.loads:
            start = seg["vaddr"] & ~0xFFF
            end = (seg["vaddr"] + seg["memsz"] + 0xFFF) & ~0xFFF
            self.uc.mem_map(start, end - start)
            self.uc.mem_write(
                seg["vaddr"],
                self.elf.data[seg["off"] : seg["off"] + seg["filesz"]],
            )

    def _map_runtime(self):
        self.uc.mem_map(STACK_BASE, STACK_SIZE)
        self.uc.mem_map(HEAP_BASE, HEAP_SIZE)
        self.uc.mem_map(SENTINEL_BASE, SENTINEL_SIZE)
        self.uc.mem_map(RETURN_TRAP, 0x1000)
        self.uc.reg_write(UC_ARM_REG_SP, STACK_BASE + STACK_SIZE - 0x100)

    # ---------- imports ----------
    def _install_imports(self):
        relocs = self.elf.relocations(".rel.plt")
        for i, r in enumerate(relocs):
            sentinel = SENTINEL_BASE + i * 16
            self.uc.mem_write(r["offset"], struct.pack("<I", sentinel))
            fn = getattr(self, "_imp_" + r["name"].split("@")[0], self._imp_unknown)
            self.handlers[sentinel] = (r["name"], fn)
        # GLOB_DAT: stack canary / weak symbols
        for r in self.elf.relocations(".rel.dyn"):
            if r["type"] == 21:  # R_ARM_GLOB_DAT
                if "stack_chk_guard" in r["name"]:
                    guard = GUARD_ADDR
                    self.uc.mem_map(guard, 0x1000)
                    self.wr(guard, struct.pack("<I", 0xDEADBEEF))
                    self.uc.mem_write(r["offset"], struct.pack("<I", guard))
                else:
                    self.uc.mem_write(r["offset"], struct.pack("<I", 0))

    def _regs(self):
        return [self.uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]

    def _stack_arg(self, index):
        """AAPCS: argument 5+ lives at [sp + 4*(index-5)] at callee entry."""
        sp = self.uc.reg_read(UC_ARM_REG_SP)
        return self.rd32(sp + 4 * (index - 5))

    def _on_code(self, uc, address, size, user):
        if address == self.trace:
            print(
                "TRACE pc=%08x r0=%08x r1=%08x r2=%08x r3=%08x lr=%08x"
                % (
                    address,
                    uc.reg_read(UC_ARM_REG_R0),
                    uc.reg_read(UC_ARM_REG_R1),
                    uc.reg_read(UC_ARM_REG_R2),
                    uc.reg_read(UC_ARM_REG_R3),
                    uc.reg_read(UC_ARM_REG_LR),
                )
            )

    def _on_sentinel(self, uc, address, size, user):
        h = self.handlers.get(address)
        if h is not None:
            name, fn = h
            ret = fn(uc, *self._regs())
            if ret is not None:
                uc.reg_write(UC_ARM_REG_R0, ret & 0xFFFFFFFF)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
            if self.verbose:
                print("call %s -> %r" % (name, ret))
            return

    def _on_unmapped(self, uc, access, address, size, value, user):
        print("UNMAPPED access=%d addr=%08x size=%d pc=%08x" % (access, address, size, uc.reg_read(UC_ARM_REG_PC)))
        return False

    # ---------- helpers ----------
    def map_region(self, addr, size):
        from unicorn import UcError

        start = addr & ~0xFFF
        length = (addr + size - start + 0xFFF) & ~0xFFF
        try:
            self.uc.mem_map(start, length)
        except UcError:
            pass

    def rd(self, addr, n):
        return bytes(self.uc.mem_read(addr, n))

    def wr(self, addr, data):
        self.uc.mem_write(addr, bytes(data))

    def rd32(self, addr):
        return struct.unpack("<I", self.rd(addr, 4))[0]

    def wr32(self, addr, v):
        self.wr(addr, struct.pack("<I", v & 0xFFFFFFFF))

    def rdstr(self, addr, limit=256):
        out = b""
        for i in range(limit):
            b = self.rd(addr + i, 1)
            if b == b"\0":
                break
            out += b
        return out.decode("latin-1")

    def malloc(self, n):
        n = (n + 7) & ~7
        p = self.heap_ptr
        self.heap_ptr += n
        if self.heap_ptr > HEAP_BASE + HEAP_SIZE:
            raise RuntimeError("heap exhausted")
        return p

    # ---------- import handlers ----------
    def _imp_unknown(self, uc, r0, r1, r2, r3):
        name = None
        for sent, (n, _f) in self.handlers.items():
            if sent == uc.reg_read(UC_ARM_REG_PC):
                name = n
        print("!! unhandled import %s" % name)
        return 0

    def _imp_memcpy(self, uc, dst, src, n, r3):
        self.wr(dst, self.rd(src, n))
        return dst

    def _imp_memmove(self, uc, dst, src, n, r3):
        self.wr(dst, self.rd(src, n))
        return dst

    def _imp_memset(self, uc, dst, val, n, r3):
        self.wr(dst, bytes([val & 0xFF]) * n)
        return dst

    def _imp_strlen(self, uc, s, r1, r2, r3):
        return len(self.rdstr(s, 0x1000))

    def _imp_malloc(self, uc, n, r1, r2, r3):
        return self.malloc(n)

    def _imp_calloc(self, uc, nmemb, size, r2, r3):
        p = self.malloc(nmemb * size)
        self.wr(p, b"\0" * (nmemb * size))
        return p

    def _imp_free(self, uc, p, r1, r2, r3):
        return 0

    def _imp_printf(self, uc, fmt, r1, r2, r3):
        print("printf:", self.rdstr(fmt))
        return 0

    def _imp_puts(self, uc, s, r1, r2, r3):
        print("puts:", self.rdstr(s))
        return 0

    def _imp_SHA1(self, uc, data, n, md, r3):
        if md:
            self.wr(md, hashlib.sha1(self.rd(data, n)).digest())
        return md

    def _imp_SHA256(self, uc, data, n, md, r3):
        if md:
            self.wr(md, hashlib.sha256(self.rd(data, n)).digest())
        return md

    def _imp_SHA512(self, uc, data, n, md, r3):
        if md:
            self.wr(md, hashlib.sha512(self.rd(data, n)).digest())
        return md

    def _imp_abort(self, uc, *a):
        raise RuntimeError("abort() called at pc=%08x" % uc.reg_read(UC_ARM_REG_PC))

    def _imp___stack_chk_fail(self, uc, *a):
        raise RuntimeError("stack smashing detected")

    def _imp_exit(self, uc, code, *a):
        raise RuntimeError("exit(%d)" % code)

    # ---------- run ----------
    def call(self, pc, args=(), thumb=False, lr=RETURN_TRAP, timeout=0, count=0):
        if thumb:
            pc |= 1
        for reg, val in zip(
            (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), args
        ):
            self.uc.reg_write(reg, val)
        self.uc.reg_write(UC_ARM_REG_LR, lr)
        self.uc.emu_start(pc, lr, timeout=timeout, count=count)
        return self.uc.reg_read(UC_ARM_REG_R0)


def main():
    path = sys.argv[1]
    pc = int(sys.argv[2], 0)
    args = []
    thumb = False
    for a in sys.argv[3:]:
        if a == "--thumb":
            thumb = True
        else:
            args.append(int(a, 0))
    e = Emu(path, verbose=True)
    ret = e.call(pc, args, thumb=thumb)
    print("returned r0=%08x" % ret)


if __name__ == "__main__":
    main()
