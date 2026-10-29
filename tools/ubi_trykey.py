#!/usr/bin/env python3
"""Check a candidate key against the encrypted `rootfs` volume.

Decrypts the first logical erase block in ECB, then looks for a UBIFS node
magic: the layer keeps `38 26 90 05` in front of the payload, so the candidate
key is accepted only when a known structure appears behind it.

Usage:
    python3 ubi_trykey.py vol0.ubi_leb --key 0011..ee
    python3 ubi_trykey.py vol0.ubi_leb --key 0011..ee --skip 8 --raw
"""
import argparse
import sys

CRYPTO = bytes.fromhex("38269005")
UBIFS = bytes.fromhex("31181006")


def decrypt(key, data):
    try:
        from Crypto.Cipher import AES
    except ImportError:
        sys.exit("pycryptodome is required: pip install pycryptodome")
    if len(key) not in (16, 24, 32):
        sys.exit(f"key must be 16/24/32 bytes, got {len(key)}")
    return AES.new(key, AES.MODE_ECB).decrypt(data[: len(data) // 16 * 16])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("leb", help="file with logical erase blocks (vol0.ubi_leb)")
    ap.add_argument("--key", required=True, help="hex key")
    ap.add_argument("--skip", type=int, default=8, help="crypto header length (default 8)")
    ap.add_argument("--probe", type=int, default=4096, help="bytes to decrypt")
    args = ap.parse_args()

    key = bytes.fromhex(args.key)
    blob = open(args.leb, "rb").read()
    head = blob[:args.probe]
    if head[:4] == CRYPTO:
        head = head[args.skip:]
    elif head[:4] != UBIFS:
        print("note: first LEB has no crypto marker, checking as is")

    plain = decrypt(key, head)
    print(f"key {len(key)*8} bit, decrypted {len(plain)} bytes")
    print("head:", plain[:64].hex())

    for off in range(0, min(256, len(plain) - 4)):
        if plain[off:off + 4] == UBIFS:
            print(f"MATCH: UBIFS node magic at +{off}")
            return 0

    printable = sum(32 <= c < 127 for c in plain[:64])
    print(f"no UBIFS magic; printable bytes in first 64: {printable}")
    print("verdict: key rejected" if printable < 40 else "verdict: inconclusive, check other modes")
    return 1


if __name__ == "__main__":
    sys.exit(main())
