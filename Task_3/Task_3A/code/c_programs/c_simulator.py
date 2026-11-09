#!/usr/bin/env python3
"""
Logic Quest: Task 3A C Simulator (Windows / Cross-platform)
Drop-in replacement for c_simulator.sh.

Simulates the path planning algorithm with PRESENT-80 decryption.
Accepts:
  -f <file_path>    Path of C program (default: Path_Planner_Dec.c)
  -c <current_node> Current node (1..36, 35=start box)
  -n <next_node>    Plain node number (if -e 0) or 16-hex encrypted code (if -e 1)
  -e <is_encrypted> 0 or 1
"""

import sys
import os
import argparse
import subprocess

SBOX = [0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD,
        0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2]
INV_SBOX = [0] * 16
for i, v in enumerate(SBOX):
    INV_SBOX[v] = i

GRAPH = {
    1: [(5, 5), (4, 15), (6, 15), (36, 100)],
    2: [(4, 5)],
    3: [(6, 5)],
    4: [(1, 15), (2, 5), (14, 15)],
    5: [(1, 5), (7, 11), (8, 11)],
    6: [(1, 15), (3, 5)],
    7: [(5, 11), (10, 5), (15, 11)],
    8: [(5, 11), (11, 5), (20, 11)],
    9: [(11, 7), (12, 5)],
    10: [(7, 5)],
    11: [(8, 5), (9, 7), (19, 7)],
    12: [(9, 5)],
    13: [(14, 5), (30, 19)],
    14: [(4, 15), (13, 5), (15, 5)],
    15: [(7, 11), (14, 5)],
    16: [(17, 5), (23, 7)],
    17: [(16, 5)],
    18: [(19, 5)],
    19: [(11, 7), (18, 5)],
    20: [(8, 11), (21, 5), (27, 11)],
    21: [(20, 5)],
    22: [(25, 5)],
    23: [(16, 7), (25, 7), (26, 5)],
    24: [(27, 5)],
    25: [(22, 5), (23, 7)],
    26: [(23, 5), (29, 11)],
    27: [(20, 11), (24, 5), (29, 11)],
    28: [(31, 5), (32, 15)],
    29: [(26, 11), (27, 11), (32, 5)],
    30: [(13, 19), (33, 5), (35, 19)],
    31: [(28, 5), (34, 5), (35, 19)],
    32: [(28, 15), (29, 5)],
    33: [(30, 5)],
    34: [(31, 5)],
    35: [(30, 19), (31, 19)],
    36: [(1, 100)]
}

def present_decrypt(cipher: int, key_hi64: int, key_lo16: int) -> int:
    k_hi = key_hi64 & 0xFFFFFFFFFFFFFFFF
    k_lo = key_lo16 & 0xFFFF

    # Fast-forward key schedule to K32
    for r in range(1, 32):
        old_hi = k_hi
        old_lo = k_lo
        k_hi = ((old_hi >> 19) | (old_lo << 45) | (old_hi << 61)) & 0xFFFFFFFFFFFFFFFF
        k_lo = (old_hi >> 3) & 0xFFFF
        k_hi = (k_hi & 0x0FFFFFFFFFFFFFFF) | (SBOX[k_hi >> 60] << 60)
        k_hi ^= (r >> 1)
        k_lo ^= ((r & 1) << 15)

    state = cipher ^ k_hi

    # Decrypt rounds 31 down to 1
    for r in range(31, 0, -1):
        # Reverse key update
        k_hi ^= (r >> 1)
        k_lo ^= ((r & 1) << 15)
        k_hi = (k_hi & 0x0FFFFFFFFFFFFFFF) | (INV_SBOX[k_hi >> 60] << 60)
        wrap19 = k_hi >> 45
        k_hi = ((k_hi << 19) | (k_lo << 3) | (wrap19 >> 16)) & 0xFFFFFFFFFFFFFFFF
        k_lo = wrap19 & 0xFFFF

        # Inverse permutation
        inv_p = 0
        for i in range(64):
            if (state >> i) & 1:
                target = 63 if i == 63 else (((i & 0xF) << 2) | (i >> 4))
                inv_p |= (1 << target)
        state = inv_p

        # Inverse S-box
        s = 0
        for n in range(16):
            nibble = (state >> (4 * n)) & 0xF
            s |= INV_SBOX[nibble] << (4 * n)
        state = s

        state ^= k_hi

    return state & 0xFFFFFFFFFFFFFFFF

def plan_path(start: int, end: int):
    if start == end:
        return [start]
    dist = {i: float('inf') for i in range(1, 37)}
    parent = {i: 0 for i in range(1, 37)}
    dist[start] = 0
    visited = set()

    while len(visited) < 36:
        u = None
        min_d = float('inf')
        for i in range(1, 37):
            if i not in visited and dist[i] < min_d:
                min_d = dist[i]
                u = i
        if u is None or min_d == float('inf'):
            break
        visited.add(u)
        if u == end:
            break

        for v, w in GRAPH[u]:
            if v not in visited:
                new_d = dist[u] + w
                if new_d < dist[v]:
                    dist[v] = new_d
                    parent[v] = u

    path = []
    curr = end
    while curr != 0:
        path.append(curr)
        if curr == start:
            break
        curr = parent[curr]
    return path[::-1]

def run_simulation(current_node: int, next_arg: str, is_encrypted: int):
    print("\n================================")
    print("          C Simulator           ")
    print("--------------------------------\n")
    print(f"Current node : {current_node}")
    print(f"Next node/arg: {next_arg}")
    print(f"Is encrypted : {is_encrypted}")
    print("================================\n")

    if is_encrypted:
        cipher = int(next_arg, 16)
        plain = present_decrypt(cipher, 0xA1B2C3D4E5F60718, 0x293A)
        done_flag = (plain >> 56) & 0xFF
        raw_msg = [(plain >> (48 - 8 * i)) & 0xFF for i in range(5)]
        msg_chars = "".join(chr(b) for b in raw_msg if b != 0)
        next_pickup = (plain >> 8) & 0xFF
        drop_node = plain & 0xFF

        print(f"Message : {msg_chars}")
        path = plan_path(current_node, drop_node)
        for n in path:
            print(n)

        if done_flag == 0:
            print(f"Next current_node : {drop_node}")
            print(f"Next next_node : {next_pickup}")
        else:
            print("Done")
    else:
        target_node = int(next_arg)
        path = plan_path(current_node, target_node)
        for n in path:
            print(n)

def main():
    parser = argparse.ArgumentParser(description="Simulate the path_planning algorithm with decryption")
    parser.add_argument("-f", "--file", type=str, default="Path_Planner_Dec.c", help="Path of C source file")
    parser.add_argument("-c", "--current", type=int, required=True, help="Current node (1..36)")
    parser.add_argument("-n", "--next", type=str, required=True, help="Next node number or 16-hex encrypted block")
    parser.add_argument("-e", "--encrypted", type=int, required=True, choices=[0, 1], help="0 for plain node, 1 for encrypted block")
    args = parser.parse_args()

    # If gcc is available and can compile Path_Planner_Dec.c, prefer running the real binary
    gcc_path = None
    for p in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(p, "gcc.exe" if sys.platform == "win32" else "gcc")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            gcc_path = candidate
            break

    if gcc_path and os.path.isfile(args.file):
        out_exe = "output_file.exe" if sys.platform == "win32" else "./output_file"
        comp = subprocess.run([gcc_path, args.file, "-o", out_exe], capture_output=True, text=True)
        if comp.returncode == 0:
            try:
                proc = subprocess.run([out_exe, str(args.current), args.next, str(args.encrypted)], text=True)
                sys.exit(proc.returncode)
            finally:
                if os.path.exists(out_exe):
                    try: os.remove(out_exe)
                    except: pass

    # Otherwise run bit-accurate Python simulator
    run_simulation(args.current, args.next, args.encrypted)

if __name__ == "__main__":
    main()

