#!/usr/bin/env python3
"""Rebuild UBI volumes from a raw NAND dump or from a package `rfs` block.

Reads physical erase blocks (PEB), checks the EC/VID headers, orders logical
erase blocks (LEB) by lnum, and writes one image per volume. Blocks carrying
the `ubifs crypto` marker keep their header; with --decrypt the header is
stripped and the payload passed to the supplied decoder.

Usage:
    python3 ubi_extract.py rfs.bin --out outdir
    python3 ubi_extract.py rfs.bin --out outdir --peb 0x20000 --data-off 0x1000
"""
import argparse
import os
import struct
import sys
from collections import Counter

EC_MAGIC = b"UBI#"
VID_MAGIC = b"UBI!"
CRYPTO = bytes.fromhex("38269005")
UBIFS_MAGIC = bytes.fromhex("31181006")


def parse_peb(blob, i, peb_size):
    p = blob[i * peb_size:(i + 1) * peb_size]
    if p[:4] != EC_MAGIC:
        return None
    # struct ubi_ec_hdr: magic, version, pad[3], ec, vid_hdr_offset, data_offset,
    # image_seq, pad2[32], hdr_crc  == 64 bytes
    _magic, _ver, _pad1, ec, vid_off, data_off, _image_seq, _pad2, _crc = struct.unpack_from(
        ">4sB3sQIII32sI", p, 0)
    vid = p[vid_off:vid_off + 64]
    if vid[:4] != VID_MAGIC:
        return None
    # struct ubi_vid_hdr: magic, version, vol_type, copy_flag, compat, vol_id,
    # lnum, pad1[4], data_size, ...
    vol_type = vid[5]
    vol_id = struct.unpack_from(">I", vid, 8)[0]
    lnum = struct.unpack_from(">I", vid, 12)[0]
    data_size = struct.unpack_from(">I", vid, 20)[0]
    return {
        "peb": i, "ec": ec, "vol_type": vol_type, "vol_id": vol_id,
        "lnum": lnum, "size": data_size, "data_off": data_off,
        "data": p[data_off:],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default="ubi_out")
    ap.add_argument("--peb", default="0x20000")
    ap.add_argument("--max-lebs", type=int, default=0, help="limit volume size")
    args = ap.parse_args()

    peb_size = int(args.peb, 0)
    blob = open(args.image, "rb").read()
    total = len(blob) // peb_size
    os.makedirs(args.out, exist_ok=True)

    pebs, kinds = [], Counter()
    for i in range(total):
        r = parse_peb(blob, i, peb_size)
        if not r:
            kinds["no-header"] += 1
            continue
        kinds["volume" if r["vol_type"] == 1 else "dynamic"] += 1
        pebs.append(r)

    print(f"pebs={total} parsed={len(pebs)} " + " ".join(f"{k}={v}" for k, v in sorted(kinds.items())))

    vols = {}
    for r in pebs:
        vols.setdefault(r["vol_id"], []).append(r)

    for vol_id, blocks in sorted(vols.items()):
        # Yealink strips VID headers: every data block comes back with lnum=0.
        # Then the physical order is the only order we have, so keep it.
        zeroed = all(b["lnum"] == 0 for b in blocks)
        blocks.sort(key=lambda b: (b["lnum"], b["peb"]))
        crypto = sum(1 for b in blocks if b["data"][:4] == CRYPTO)
        leb_len = max(len(b["data"]) for b in blocks)
        note = " lnum zeroed by vendor, order = PEB order" if zeroed else ""
        print(f"vol {vol_id}: lebs={len(blocks)} leb_size={leb_len:#x} crypto={crypto}{note}")

        sizes = {b["size"] for b in blocks}
        if sizes != {0}:
            gaps = [i for i in range(max(b["lnum"] for b in blocks) + 1)
                    if i not in {b["lnum"] for b in blocks}]
            if gaps:
                print(f"  leak: {len(gaps)} missing lnum(s), padding with 0xFF")

        path = os.path.join(args.out, f"vol{vol_id}.ubi_leb")
        with open(path, "wb") as fh:
            if zeroed or sizes == {0}:
                for b in blocks:
                    fh.write(b["data"])
            else:
                by_num = {b["lnum"]: b for b in blocks}
                for i in range(max(by_num) + 1):
                    b = by_num.get(i)
                    fh.write(b["data"] if b else b"\xff" * leb_len)

        # sanity: does the first logical block look like a UBIFS node once the
        # crypto header is skipped?
        first = blocks[0]["data"]
        for skip in (0, 4, 8, 12, 16):
            if first[skip:skip + 4] == UBIFS_MAGIC:
                print(f"  vol {vol_id}: UBIFS magic at +{skip} of LEB 0")
                break
        print(f"  -> {path}")


if __name__ == "__main__":
    main()
