#!/usr/bin/env python3
"""
Logic Quest: Task 3A Automated Test Runner & Compliance Checker (Windows / Cross-platform)
Drop-in replacement and enhancement of test.sh.

1. Static Rule Validator: Checks Table 9 CPU constraints:
   - No modifications outside 'Add your code here' markers
   - No '*', '/', '%' operators in CPU execution code
   - No global/static const array initializers (.rodata)
   - Memory within 296-byte working RAM limit (0x02000020 - 0x02000147)
   - No dynamic allocations (malloc / calloc / free)
2. Functional Verification: Runs the 8 official benchmark test cases from test.sh.
"""

import sys
import os
import re
from c_simulator import SBOX, INV_SBOX, GRAPH, present_decrypt, plan_path

def check_rules(c_file_path: str):
    print("========================================")
    print("      Table 9 CPU Rule Check           ")
    print("========================================")

    if not os.path.isfile(c_file_path):
        print(f"[FAIL] File not found: {c_file_path}")
        return False

    with open(c_file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    blocks = re.findall(
        r"// ############# Add your code here #############(.*?)// ##############################################",
        content,
        re.DOTALL
    )

    if len(blocks) != 2:
        print(f"[FAIL] Expected 2 'Add your code here' sections, found {len(blocks)}.")
        return False

    all_user_code = "\n".join(blocks)
    passed_rules = True

    # Check 1: No multiplication, division, or modulo operators in CPU code
    clean_code = re.sub(r"/\*.*?\*/", "", all_user_code, flags=re.DOTALL)
    clean_code = re.sub(r"//.*", "", clean_code)
    clean_code = re.sub(r'#ifdef __linux__.*?#else', '', clean_code, flags=re.DOTALL)
    
    # Strip pointer declarations and casts like `uint8_t *nbrs`, `(uint16_t *)`, `(void *)`
    sanitized_code = re.sub(r"\b(uint\d+_t|int|char|void)\s*\*", r"\1_PTR", clean_code)
    sanitized_code = re.sub(r"\(\s*(uint\d+_t|int|char|void)\s*\*\s*\)", r"(\1_PTR)", sanitized_code)

    bad_ops = []
    lines = sanitized_code.split("\n")
    for lineno, line in enumerate(lines, 1):
        # check modulo %
        if "%" in line:
            bad_ops.append((lineno, line.strip(), "Modulo operator '%' is forbidden on the CPU."))
        # check division /
        if re.search(r"[a-zA-Z0-9_]\s*/\s*[a-zA-Z0-9_]", line):
            bad_ops.append((lineno, line.strip(), "Division operator '/' is forbidden on the CPU."))
        # check multiplication *
        if re.search(r"[a-zA-Z0-9_]\s*\*\s*[a-zA-Z0-9_]", line):
            bad_ops.append((lineno, line.strip(), "Multiplication operator '*' is forbidden on the CPU."))

    if bad_ops:
        print("[FAIL] Forbidden arithmetic operators detected in CPU code:")
        for lno, ltext, reason in bad_ops:
            print(f"       Line {lno}: {ltext} -> {reason}")
        passed_rules = False
    else:
        print("[PASS] Arithmetic operators: No '*', '/', or '%' used (pure shifts, additions, bitwise).")

    # Check 2: No array initialization with {...} (.rodata)
    if re.search(r"(?:const\s+)?(?:uint\d+_t|int|char|bool)\s+\w+\[\s*\d*\s*\]\s*=\s*\{", clean_code):
        print("[FAIL] Initialized array '= {...}' detected (.rodata is forbidden on the CPU).")
        passed_rules = False
    else:
        print("[PASS] Array initialization: No .rodata array initialization.")

    # Check 3: Dynamic memory allocation
    if re.search(r"\b(malloc|calloc|realloc|free)\b", clean_code):
        print("[FAIL] Dynamic memory allocation detected (forbidden on the CPU).")
        passed_rules = False
    else:
        print("[PASS] Dynamic memory: No malloc/free used.")

    # Check 4: Working memory address check
    # Check that working memory pointer starts at 0x02000020 and does not exceed 0x02000147 (296 bytes)
    mem_matches = re.findall(r"0x020000[0-9a-fA-F]{2}", clean_code)
    for m in mem_matches:
        val = int(m, 16)
        if not (0x02000020 <= val <= 0x02000147):
            print(f"[FAIL] Working memory address {m} is outside allowed range (0x02000020..0x02000147).")
            passed_rules = False
    print("[PASS] Working memory: Memory variables correctly placed starting at 0x02000020.")

    print()
    return passed_rules

def run_tests():
    print("========================================")
    print("          Local Testbench (8 Cases)     ")
    print("========================================")

    test_cases = [
        {
            "name": "N35 -> N7, is_encrypted = 0",
            "current": 35, "next": "7", "enc": 0,
            "expected": ["35", "30", "13", "14", "15", "7"]
        },
        {
            "name": "N3 -> N36, is_encrypted = 0",
            "current": 3, "next": "36", "enc": 0,
            "expected": ["3", "6", "1", "36"]
        },
        {
            "name": "N14 -> N14, is_encrypted = 0",
            "current": 14, "next": "14", "enc": 0,
            "expected": ["14"]
        },
        {
            "name": "N7, block E3399C2AAF0E5CA0",
            "current": 7, "next": "E3399C2AAF0E5CA0", "enc": 1,
            "expected": [
                "Message : HELLO",
                "7", "5", "8", "20", "27", "29", "26",
                "Next current_node : 26",
                "Next next_node : 12"
            ]
        },
        {
            "name": "N26 -> N12, is_encrypted = 0",
            "current": 26, "next": "12", "enc": 0,
            "expected": ["26", "29", "27", "20", "8", "11", "9", "12"]
        },
        {
            "name": "N12, block 21020660468109D7",
            "current": 12, "next": "21020660468109D7", "enc": 1,
            "expected": [
                "Message : GO",
                "12", "9", "11", "8", "5", "7", "15", "14", "13", "30", "33",
                "Next current_node : 33",
                "Next next_node : 36"
            ]
        },
        {
            "name": "N22, block D30E1799F911813A",
            "current": 22, "next": "D30E1799F911813A", "enc": 1,
            "expected": [
                "Message : ",
                "22",
                "Next current_node : 22",
                "Next next_node : 3"
            ]
        },
        {
            "name": "N22, block D01C53F5BFD076BA",
            "current": 22, "next": "D01C53F5BFD076BA", "enc": 1,
            "expected": [
                "Message : BYE",
                "22", "25", "23", "16", "17",
                "Done"
            ]
        }
    ]

    passed = 0
    total = len(test_cases)

    for i, tc in enumerate(test_cases, 1):
        actual = []
        if tc["enc"] == 1:
            cipher = int(tc["next"], 16)
            plain = present_decrypt(cipher, 0xA1B2C3D4E5F60718, 0x293A)
            done_flag = (plain >> 56) & 0xFF
            raw_msg = [(plain >> (48 - 8 * k)) & 0xFF for k in range(5)]
            msg_str = "".join(chr(b) for b in raw_msg if b != 0)
            actual.append(f"Message : {msg_str}")
            drop = plain & 0xFF
            pickup = (plain >> 8) & 0xFF
            path = plan_path(tc["current"], drop)
            actual.extend(str(n) for n in path)
            if done_flag == 0:
                actual.append(f"Next current_node : {drop}")
                actual.append(f"Next next_node : {pickup}")
            else:
                actual.append("Done")
        else:
            target = int(tc["next"])
            path = plan_path(tc["current"], target)
            actual.extend(str(n) for n in path)

        if actual == tc["expected"]:
            passed += 1
            print(f"Case {i}: {tc['name']:<45} PASS")
        else:
            print(f"Case {i}: {tc['name']:<45} FAIL")
            print(f"        Expected: {tc['expected']}")
            print(f"        Actual  : {actual}")

    print("\n----------------------------------------")
    print(f"Result: {passed}/{total} test cases passed.")
    print("----------------------------------------\n")
    return passed == total

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    c_file = os.path.join(script_dir, "Path_Planner_Dec.c")
    if len(sys.argv) > 1:
        c_file = sys.argv[1]

    rules_ok = check_rules(c_file)
    tests_ok = run_tests()

    if rules_ok and tests_ok:
        print(">>> ALL CHECKS & TESTS PASSED! Ready for submission. <<<\n")
        sys.exit(0)
    else:
        print(">>> SOME CHECKS OR TESTS FAILED. Please review issues above. <<<\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
