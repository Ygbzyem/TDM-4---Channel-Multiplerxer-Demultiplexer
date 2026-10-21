"""One command: simulate the RTL with Icarus Verilog, then compare with the
Python golden model.

    python golden_model/run_verification.py
    python golden_model/run_verification.py --vectors input/random_vectors.hex
    python golden_model/run_verification.py --no-sim      # compare existing result files

Works from any directory. Exit code: 0 = PASS, 1 = FAIL, 2 = tool/sim problem.

--no-sim is for Vivado users: run tb_tdm_top_filebased.v in XSIM (Run All),
make the 3 result files appear in golden_model/verification_logs/, then run
this script with --no-sim. See golden_model/README.md.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import compare_output

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TB = ROOT / "techbench" / "tb_tdm_top_filebased.v"
SIM = ROOT / "sim_filebased"          # listed in .gitignore


def find_tool(name):
    from shutil import which

    found = which(name)
    if found:
        return found

    exe = name + (".exe" if os.name == "nt" else "")
    for base in (
        r"C:\iverilog\bin",
        r"C:\Program Files\iverilog\bin",
        r"C:\Program Files (x86)\iverilog\bin",
        "/usr/local/bin",
        "/usr/bin",
    ):
        cand = Path(base) / exe
        if cand.exists():
            return str(cand)
    return None


def simulate(vectors, paths):
    iverilog, vvp = find_tool("iverilog"), find_tool("vvp")
    if not iverilog or not vvp:
        print("ERROR: iverilog/vvp not found.")
        print("  Install Icarus Verilog (https://bleyer.org/icarus/) and re-open the terminal,")
        print("  or simulate in Vivado and use --no-sim (see golden_model/README.md).")
        return False

    sources = [str(p) for p in sorted((ROOT / "src").glob("*.v"))]
    paths["hex"].parent.mkdir(parents=True, exist_ok=True)

    print("[1/2] compiling RTL + testbench ...")
    r = subprocess.run(
        [iverilog, "-g2012", "-o", str(SIM), str(TB), *sources],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        return False

    print("[2/2] running simulation ...")
    r = subprocess.run(
        [
            vvp, str(SIM),
            f"+INPUT={vectors}",
            f"+OUT_HEX={paths['hex']}",
            f"+OUT_STREAM={paths['stream']}",
            f"+OUT_LAT={paths['lat']}",
        ],
        cwd=ROOT, capture_output=True, text=True,
    )
    for line in r.stdout.splitlines():
        if "FAIL" in line or "ERROR" in line or "TONG KET" in line or "loaded" in line:
            print("   ", line.strip())
    if r.returncode != 0 or "ERROR" in r.stdout:
        print(r.stdout + r.stderr)
        return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vectors", default=str(compare_output.DEFAULT_INPUT))
    ap.add_argument("--no-sim", action="store_true",
                    help="skip the Icarus run, only compare existing result files")
    args = ap.parse_args(argv)

    vectors = Path(args.vectors).resolve()
    if not vectors.exists():
        print(f"ERROR: input file not found: {vectors}")
        return 2

    paths = compare_output.default_paths(vectors)

    if not args.no_sim and not simulate(vectors, paths):
        return 2

    ok = compare_output.run_comparison(
        vectors, paths["hex"], paths["stream"], paths["lat"], paths["report"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
