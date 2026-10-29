#!/usr/bin/env python3
"""Probe the UBI volume extracted from a Yealink package.

Classifies physical erase blocks (PEBs) and reports what the encrypted ones
look like: repeated ciphertext blocks, leftovers of plaintext, per-PEB metadata.
"""
import sys
from collections import Counter

PEB = 0x20000
DATA_OFF = 0x1000
CRYPTO_MAGIC = bytes.fromhex("38269005")
UBI_EC = "UBI#".encode()
UBI_VID = "UBI!".encode()
UBIFS_NODE = bytes.fromhex("31181006")  # little-endian node magic


def main(path):
    blob = open(path, "rb").read()
    pebs = len(blob) // PEB
    kinds = Counter()
    crypto = []
    for i in range(pebs):
        p = blob[i * PEB:(i + 1) * PEB]
        if p[:4] == UBI_EC:
            data = p[DATA_OFF:]
            if data[:4] == CRYPTO_MAGIC:
                kinds["crypto"] += 1
                crypto.append((i, data))
            else:
                kinds["plain"] += 1
        elif p.strip(b"\xff") == b"":
            kinds["erased"] += 1
        else:
            kinds["other"] += 1

    print(f"peb={pebs} " + " ".join(f"{k}={v}" for k, v in sorted(kinds.items())))

    if not crypto:
        return
    # what sits right after the magic?
    heads = Counter(d[4:20] for _, d in crypto)
    print(f"distinct 16-byte headers after magic: {len(heads)} of {len(crypto)}")

    # do encrypted blocks repeat? compare first 16-byte ciphertext block
    first = Counter(d[4:20] for _, d in crypto)
    top, n = first.most_common(1)[0]
    print(f"most common first block appears {n}x: {top.hex()}")

    # repeated 16-byte blocks anywhere in the first 4 KiB of a PEB
    for idx, d in crypto[:3]:
        chunk = d[:4096]
        blocks = [chunk[j:j + 16] for j in range(0, len(chunk) - 15, 16)]
        c = Counter(blocks)
        bt, bn = c.most_common(1)[0]
        print(f"peb {idx}: unique16={len(c)}/{len(blocks)} top={bn}x {bt.hex()}")

    # any leftover plaintext structures?
    hits = 0
    for idx, d in crypto:
        if UBIFS_NODE in d[:512] or UBIFS_NODE in d[-512:]:
            hits += 1
    print(f"pebs with UBIFS node magic near edges: {hits}")

    # entropy of one sample
    import math
    sample = crypto[0][1][:8192]
    freq = Counter(sample)
    ent = -sum((v / len(sample)) * math.log2(v / len(sample)) for v in freq.values())
    print(f"entropy of first 8 KiB: {ent:.3f} bits/byte")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "old/108.86.0.118.rfs.bin")
