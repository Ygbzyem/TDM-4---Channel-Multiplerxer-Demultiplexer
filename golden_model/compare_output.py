"""Compare the RTL simulation results with the Python golden model.

For EVERY test vector in the input .hex file this script checks:

  1. BIT STREAM  - the 32 bits the RTL put on TDM_DATA (one full frame,
                   captured from bit_count == 0) equal, cycle by cycle,
                   the stream produced by golden_model.serialize().
  2. OUTPUTS     - the settled CH0_OUT..CH3_OUT written by the RTL equal the
                   channels the golden model recovers.
  3. LATENCY     - the latency measured by the RTL testbench is inside the
                   architecture's worst-case bound (latency_checker.py).

Inputs  (written by techbench/tb_tdm_top_filebased.v):
    verification_logs/rtl_output_<tag>.hex
    verification_logs/rtl_stream_<tag>.txt
    verification_logs/rtl_latency_<tag>.txt
Output: verification_logs/verification_report[_<tag>].md   (real results)

Works from any directory. Exit code: 0 = all PASS, 1 = at least one FAIL.
"""

import argparse
import sys
from pathlib import Path

from golden_model import TDMGoldenModel
from timing_checker import check_frame_length
from latency_checker import check_latency, report_latency
from report_generator import write_report

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOGS = HERE / "verification_logs"
DEFAULT_INPUT = ROOT / "input" / "input_vectors.hex"


def default_paths(input_file):
    """Result-file names for a given input file (input_vectors.hex keeps the
    original committed names; any other file gets its own <stem> tag)."""

    input_file = Path(input_file)
    tag = "vectors" if input_file.name == "input_vectors.hex" else input_file.stem

    return {
        "hex": LOGS / f"rtl_output_{tag}.hex",
        "stream": LOGS / f"rtl_stream_{tag}.txt",
        "lat": LOGS / f"rtl_latency_{tag}.txt",
        "xlsx": LOGS / (
            "verification_results.xlsx" if tag == "vectors"
            else f"verification_results_{tag}.xlsx"
        ),
        "report": LOGS / (
            "verification_report.md" if tag == "vectors"
            else f"verification_report_{tag}.md"
        ),
    }


def read_lines(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Cannot find {path}\n"
            "  -> run the RTL simulation first "
            "(python golden_model/run_verification.py)"
        )

    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("//")[0].strip()      # same comment style as $readmemh
        if line:
            lines.append(line)
    return lines


def split_channels(word):
    return (
        (word >> 24) & 0xFF,
        (word >> 16) & 0xFF,
        (word >> 8) & 0xFF,
        word & 0xFF,
    )


def compare_vector(index, in_hex, rtl_stream, rtl_out, latency, gm):
    """Compare ONE vector against the golden model. Returns a result dict."""

    chs = split_channels(int(in_hex, 16))
    golden = gm.run_frame(*chs)
    golden_stream = golden["stream"]

    # --- 1) bit stream, cycle by cycle -------------------------------
    bad_cycle = None
    expected_bit = actual_bit = None

    if not check_frame_length(golden_stream, verbose=False):
        bad_cycle = 0                          # golden model itself is broken

    for cycle in range(max(len(golden_stream), len(rtl_stream))):
        exp = str(golden_stream[cycle]) if cycle < len(golden_stream) else "<none>"
        act = rtl_stream[cycle] if cycle < len(rtl_stream) else "<none>"
        if exp != act:
            bad_cycle, expected_bit, actual_bit = cycle, exp, act
            break

    # --- 2) settled outputs ------------------------------------------
    golden_out = "{:02x}{:02x}{:02x}{:02x}".format(
        golden["ch0_out"], golden["ch1_out"], golden["ch2_out"], golden["ch3_out"]
    )
    out_ok = rtl_out.lower() == golden_out

    stream_ok = bad_cycle is None

    return {
        "index": index,
        "input": in_hex.lower(),
        "stream_ok": stream_ok,
        "bad_cycle": bad_cycle,
        "expected_bit": expected_bit,
        "actual_bit": actual_bit,
        "out_ok": out_ok,
        "golden_out": golden_out,
        "rtl_out": rtl_out.lower(),
        "latency": latency,
        "golden_stream": "".join(str(b) for b in golden_stream),
        "rtl_stream": rtl_stream,
        "ok": stream_ok and out_ok,
    }


def run_comparison(input_file, hex_file, stream_file, lat_file, report_file,
                   excel_file=None, simulator=""):
    """Returns True when every check passes. excel_file: also write an .xlsx workbook."""

    inputs = read_lines(input_file)
    outs = read_lines(hex_file)
    streams = read_lines(stream_file)
    lats = [int(x) for x in read_lines(lat_file)]

    n = len(inputs)
    if not (len(outs) == len(streams) == len(lats) == n):
        print("\n[FAIL] result files do not have the same number of lines as the input:")
        print(f"  input vectors : {n}")
        print(f"  rtl_output    : {len(outs)}")
        print(f"  rtl_stream    : {len(streams)}")
        print(f"  rtl_latency   : {len(lats)}")
        print("  -> re-run the simulation (the run may have been cut short).")
        return False

    gm = TDMGoldenModel()

    print("\n" + "=" * 62)
    print(" RTL vs GOLDEN MODEL")
    print("=" * 62)
    print(f" input vectors : {input_file}")
    print(f" vectors       : {n}\n")

    results = []
    for i in range(n):
        r = compare_vector(i, inputs[i], streams[i], outs[i], lats[i], gm)
        results.append(r)

        tag = "PASS" if r["ok"] else "FAIL"
        print(
            f"[{tag}] #{i:<3} in={r['input']}  "
            f"stream={'OK' if r['stream_ok'] else 'BAD'}  "
            f"out={'OK' if r['out_ok'] else 'BAD'}  "
            f"latency={r['latency']}"
        )
        if not r["stream_ok"]:
            print(f"        first wrong cycle {r['bad_cycle']}: "
                  f"golden={r['expected_bit']} rtl={r['actual_bit']}")
        if not r["out_ok"]:
            print(f"        CHx_OUT golden={r['golden_out']} rtl={r['rtl_out']}")

    latency = check_latency(lats)
    report_latency(latency)

    passed = sum(1 for r in results if r["ok"])
    all_pass = (passed == n) and latency["ok"]

    print("\n" + "=" * 62)
    print(f" vectors passed : {passed}/{n}")
    print(f" latency check  : {'PASS' if latency['ok'] else 'FAIL'}")
    print("=" * 62)
    print(">>> ALL CHECKS PASSED" if all_pass else ">>> VERIFICATION FAILED")

    write_report(
        report_file,
        {
            "input_file": Path(input_file).name,
            "results": results,
            "latency": latency,
            "all_pass": all_pass,
        },
    )
    print(f"\nReport written: {report_file}")

    if excel_file:
        try:
            import export_excel
            summary = {"input_file": Path(input_file).name, "results": results,
                       "latency": latency, "all_pass": all_pass}
            export_excel.write_excel(excel_file, summary, simulator)
            print(f"Excel written : {excel_file}")
        except ImportError:
            print("Excel skipped : install openpyxl to get the .xlsx workbook  ->  pip install openpyxl")

    return all_pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vectors", default=str(DEFAULT_INPUT),
                    help="input .hex file the RTL was simulated with")
    args = ap.parse_args(argv)

    p = default_paths(args.vectors)
    ok = run_comparison(args.vectors, p["hex"], p["stream"], p["lat"], p["report"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
