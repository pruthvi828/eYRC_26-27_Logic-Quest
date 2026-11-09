#!/usr/bin/env python3
"""
Logic Quest: Task 3A Encrypted Code Generator (Windows / Cross-platform)
Drop-in replacement for encrypt.sh.

Encrypts an 8-byte plaintext block with PRESENT-80 cipher (Key: A1 B2 C3 D4 E5 F6 07 18 29 3A).
Block layout (8 bytes, MSB first):
  byte 0    : done flag (0, or 1 for last drop)
  byte 1..5 : message, up to 5 ASCII chars (0x00 padding)
  byte 6    : next pick-up node (1..36, or 0 if done=1)
  byte 7    : drop node (1..36)
"""

import sys
import argparse

SBOX = [0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD,
        0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2]

def present_encrypt(state: int, key_hi64: int, key_lo16: int) -> int:
    k_hi = key_hi64 & 0xFFFFFFFFFFFFFFFF
    k_lo = key_lo16 & 0xFFFF

    for round_num in range(1, 32):
        # 1. Add round key (64 MSBs of 80-bit key register)
        state ^= k_hi

        # 2. S-box layer
        s = 0
        for n in range(16):
            nibble = (state >> (4 * n)) & 0xF
            s |= SBOX[nibble] << (4 * n)
        state = s

        # 3. Permutation layer
        p = 0
        for i in range(64):
            if (state >> i) & 1:
                target = 63 if i == 63 else (16 * i) % 63
                p |= (1 << target)
        state = p

        # 4. Key schedule update
        old_hi = k_hi
        old_lo = k_lo
        # Rotate 80-bit register left by 61 (= right by 19)
        k_hi = ((old_hi >> 19) | (old_lo << 45) | (old_hi << 61)) & 0xFFFFFFFFFFFFFFFF
        k_lo = (old_hi >> 3) & 0xFFFF
        # S-box on bits 79..76 (top 4 bits of k_hi)
        k_hi = (k_hi & 0x0FFFFFFFFFFFFFFF) | (SBOX[k_hi >> 60] << 60)
        # XOR round_num into bits 19..15 (bits 3..0 of k_hi and bit 15 of k_lo)
        k_hi ^= (round_num >> 1)
        k_lo ^= ((round_num & 1) << 15)

    # Final round key addition K32
    return (state ^ k_hi) & 0xFFFFFFFFFFFFFFFF

def make_code(done: int, msg: str, pickup: int, drop: int):
    if done not in (0, 1):
        raise ValueError("The done flag must be 0 or 1.")
    if not (1 <= drop <= 36):
        raise ValueError("The drop node must be a node number from 1 to 36.")
    if done == 0 and not (1 <= pickup <= 36):
        raise ValueError("The next pick-up node must be a node number from 1 to 36 (when done flag is 0).")
    if done == 1 and not (0 <= pickup <= 36):
        raise ValueError("The next pick-up node must be 0, or 1 to 36 (when done flag is 1).")
    if len(msg) > 5:
        raise ValueError("The message can have at most 5 characters.")

    plain = (done & 0xFF) << 56
    for i, ch in enumerate(msg):
        val = ord(ch)
        if val < 0x20 or val > 0x7E:
            raise ValueError("The message can only contain printable ASCII characters.")
        plain |= (val & 0xFF) << (48 - 8 * i)
    plain |= (pickup & 0xFF) << 8
    plain |= (drop & 0xFF)

    cipher = present_encrypt(plain, 0xA1B2C3D4E5F60718, 0x293A)

    print(f"Done flag       : {done}")
    print(f"Message         : {msg}")
    print(f"Next pick-up    : {pickup}")
    print(f"Drop node       : {drop}")
    print(f"Plain block     : {plain:016X}")
    print(f"Encrypted block : {cipher:016X}")
    return plain, cipher

def main():
    parser = argparse.ArgumentParser(description="Make encrypted input blocks for Task 3A")
    parser.add_argument("-f", "--flag", type=int, required=True, help="Done flag: 0, or 1 for last block")
    parser.add_argument("-m", "--message", type=str, default="", help="Message, up to 5 characters")
    parser.add_argument("-p", "--pickup", type=int, default=0, help="Next pick-up node (1..36)")
    parser.add_argument("-d", "--drop", type=int, required=True, help="Drop node (1..36)")
    args = parser.parse_args()

    try:
        make_code(args.flag, args.message, args.pickup, args.drop)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

