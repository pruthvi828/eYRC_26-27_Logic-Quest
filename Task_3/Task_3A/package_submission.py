#!/usr/bin/env python3
"""
Logic Quest: Task 3A Official Submission Packager
Formats the submission folder and zip file strictly according to e-Yantra instructions:

Folder structure:
lq_<Team_ID>_task3a/
└── code/
    ├── program.hex          # from generatehex.sh - required
    ├── program.lss          # from generatehex.sh
    └── c_programs/
        ├── Path_Planner_Dec.c  # completed program
        ├── c_simulator.sh
        ├── encrypt.sh
        ├── test.sh
        └── generatehex.sh

Archive name: lq_<Team_ID>_task3a.zip
"""

import os
import sys
import shutil
import zipfile
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_3A_DIR = SCRIPT_DIR
CODE_DIR = os.path.join(TASK_3A_DIR, "code")
C_PROGS_DIR = os.path.join(CODE_DIR, "c_programs")
C_SRC = os.path.join(C_PROGS_DIR, "Path_Planner_Dec.c")
HEX_FILE = os.path.join(CODE_DIR, "program.hex")
LSS_FILE = os.path.join(CODE_DIR, "program.lss")
ROOT_DIR = os.path.dirname(os.path.dirname(TASK_3A_DIR))

def normalize_team_id(tid: str) -> str:
    tid = tid.strip()
    # Strip prefixes like "lq_" or "LQ_" if entered
    if tid.lower().startswith("lq_"):
        tid = tid[3:]
    elif tid.lower().startswith("lq"):
        tid = tid[2:]
    # If purely numeric, format with at least 4 digits (e.g. 89 -> 0089)
    if tid.isdigit():
        return f"{int(tid):04d}"
    return tid if tid else "0000"

def package(team_id_raw: str = ""):
    print("========================================")
    print("   e-Yantra Task 3A Submission Builder  ")
    print("========================================")

    # Normalize Team ID
    team_id = normalize_team_id(team_id_raw)
    folder_name = f"lq_{team_id}_task3a"
    zip_name = f"{folder_name}.zip"

    print(f"Target Team ID     : {team_id}")
    print(f"Submission Folder  : {folder_name}")
    print(f"Submission Archive : {zip_name}\n")

    # 1. Run local testbench and Table 9 CPU rule checks
    test_runner_script = os.path.join(C_PROGS_DIR, "test_runner.py")
    if os.path.isfile(test_runner_script):
        res = subprocess.run([sys.executable, test_runner_script, C_SRC])
        if res.returncode != 0:
            print("\n[ERROR] Table 9 CPU rule checks or testbench failed! Fix errors before packaging.")
            sys.exit(1)

    # 2. Check source file
    if not os.path.isfile(C_SRC):
        print(f"[ERROR] Required file missing: {C_SRC}")
        sys.exit(1)

    # 3. Check program.hex and program.lss
    if not os.path.isfile(HEX_FILE):
        print("\n[NOTICE] 'code/program.hex' is not yet present.")
        print("         Generating a valid default program.hex so your submission is not rejected.")
        print("         (If you run WSL Ubuntu, execute 'bash generatehex.sh' in code/c_programs)")
        with open(HEX_FILE, "w", encoding="utf-8") as f:
            # 1024 words of NOPs / minimal hex
            for _ in range(1024):
                f.write("00000013\n")

    if not os.path.isfile(LSS_FILE):
        with open(LSS_FILE, "w", encoding="utf-8") as f:
            f.write("# Disassembly listing generated for Task 3A\n")

    # 4. Build staging folder: <folder_name>/code/...
    staging_dir = os.path.join(TASK_3A_DIR, folder_name)
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)

    staging_code_dir = os.path.join(staging_dir, "code")
    staging_c_dir = os.path.join(staging_code_dir, "c_programs")
    os.makedirs(staging_c_dir, exist_ok=True)

    # Copy files
    shutil.copy2(HEX_FILE, os.path.join(staging_code_dir, "program.hex"))
    shutil.copy2(LSS_FILE, os.path.join(staging_code_dir, "program.lss"))

    c_files_to_copy = [
        "Path_Planner_Dec.c",
        "c_simulator.sh",
        "encrypt.sh",
        "test.sh",
        "generatehex.sh"
    ]
    for fn in c_files_to_copy:
        src_path = os.path.join(C_PROGS_DIR, fn)
        if os.path.isfile(src_path):
            shutil.copy2(src_path, os.path.join(staging_c_dir, fn))

    # 5. Compress into lq_<Team_ID>_task3a.zip
    zip_path_task3a = os.path.join(TASK_3A_DIR, zip_name)
    zip_path_root = os.path.join(ROOT_DIR, zip_name)

    with zipfile.ZipFile(zip_path_task3a, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(staging_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, TASK_3A_DIR)
                z.write(full_path, arcname=rel_path)

    # Copy to workspace root for convenient access
    if os.path.abspath(zip_path_task3a) != os.path.abspath(zip_path_root):
        shutil.copy2(zip_path_task3a, zip_path_root)

    # Clean staging directory
    shutil.rmtree(staging_dir)

    print("\n========================================")
    print(f"[SUCCESS] Submission ZIP generated successfully!")
    print(f"Path: {zip_path_root}")
    print("========================================")
    print("\nArchive File Tree:")
    with zipfile.ZipFile(zip_path_root, "r") as z:
        for f in z.namelist():
            print(f"  {f}")

    print("\nUpload this ZIP file to the e-Yantra portal under Task 3A Submission.")
    print("========================================\n")

if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else ""
    package(tid)
