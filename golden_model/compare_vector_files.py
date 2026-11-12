"""Quick check of the settled outputs only (no bit stream, no latency).

For every input vector, the expected output is what the golden model
recovers; it is compared with the line the RTL testbench wrote to
rtl_output_vectors.hex. Use compare_output.py for the complete check.

Works from any directory. Exit code: 0 = all PASS, 1 = at least one FAIL.
"""

import argparse
import sys
from pathlib import Path

from compare_output import pack_channels, split_channels, vector_hex
from golden_model import TDMGoldenModel

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def read_hex_file(filename):
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"Cannot find file: {filename}")

    with open(path, "r") as f:
        return [line.split("//")[0].strip().lower() for line in f if line.split("//")[0].strip()]


def golden_expected(in_hex, num_channels=4, data_width=8):
    chs = split_channels(int(in_hex, 16), num_channels, data_width)
    r = TDMGoldenModel(num_channels, data_width).run_frame(*chs)
    return vector_hex(pack_channels(r["outputs"], data_width), num_channels, data_width)


def compare_files(input_file, output_file, num_channels=4, data_width=8):
    inputs = read_hex_file(input_file)
    actual = read_hex_file(output_file)

    total = max(len(inputs), len(actual))
    errors = 0

    print("\n" + "=" * 60)
    print("FILE-BASED RTL vs GOLDEN MODEL (settled outputs)")
    print("=" * 60)

    for i in range(total):
        exp = golden_expected(inputs[i], num_channels, data_width) if i < len(inputs) else "<missing>"
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
    ap.add_argument("--channels", type=int, default=4, help="NUM_CHANNELS (default 4)")
    ap.add_argument("--width", type=int, default=8, help="DATA_WIDTH (default 8)")
    args = ap.parse_args(argv)
    return 0 if compare_files(args.input, args.output, args.channels, args.width) else 1


if __name__ == "__main__":
    sys.exit(main())
