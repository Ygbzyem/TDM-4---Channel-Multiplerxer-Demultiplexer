"""Quick check of the settled outputs only (no bit stream, no latency).

For every input vector, the expected output is what the golden model
recovers; it is compared with the line the RTL testbench wrote to
rtl_output_vectors.hex. Use compare_output.py for the complete check.

Works from any directory. Exit code: 0 = all PASS, 1 = at least one FAIL.
"""

import argparse
import sys
from pathlib import Path

from golden_model import TDMGoldenModel

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def read_hex_file(filename):
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"Cannot find file: {filename}")

    with open(path, "r") as f:
        return [line.split("//")[0].strip().lower() for line in f if line.split("//")[0].strip()]


def golden_expected(in_hex):
    word = int(in_hex, 16)
    r = TDMGoldenModel().run_frame(
        (word >> 24) & 0xFF, (word >> 16) & 0xFF, (word >> 8) & 0xFF, word & 0xFF
    )
    return "{:02x}{:02x}{:02x}{:02x}".format(
        r["ch0_out"], r["ch1_out"], r["ch2_out"], r["ch3_out"]
    )


def compare_files(input_file, output_file):
    inputs = read_hex_file(input_file)
    actual = read_hex_file(output_file)

    total = max(len(inputs), len(actual))
    errors = 0

    print("\n" + "=" * 60)
    print("FILE-BASED RTL vs GOLDEN MODEL (settled outputs)")
    print("=" * 60)

    for i in range(total):
        exp = golden_expected(inputs[i]) if i < len(inputs) else "<missing>"
        act = actual[i] if i < len(actual) else "<missing>"
        ok = exp == act
        errors += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] #{i:<3} expected=0x{exp.upper()} actual=0x{act.upper()}")

    print("=" * 60)
    print(f"Total vectors : {total}   Passed : {total - errors}   Failed : {errors}")
    print(">>> ALL VECTORS PASSED" if errors == 0 else f">>> {errors} VECTOR(S) FAILED")
    return errors == 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().split("\n")[0])
    ap.add_argument("--input", default=str(ROOT / "input" / "input_vectors.hex"))
    ap.add_argument("--output", default=str(HERE / "verification_logs" / "rtl_output_vectors.hex"))
    args = ap.parse_args(argv)
    return 0 if compare_files(args.input, args.output) else 1


if __name__ == "__main__":
    sys.exit(main())
