r"""Run ONE case, written in a small text file, through the RTL and through the golden
model, and write two result files in the same format, for a side-by-side comparison by
eye. Nothing is compared automatically.

A case gives every device a whole message (hex). Each message is cut into DATA_WIDTH-bit
slots; frame f carries slot f of every channel, CH0 first, and a finished channel sends 0.

The RTL side is the existing file-driven testbench techbench/tb_tdm_top_filebased.v in
CASE_FILE mode; NUM_CHANNELS and DATA_WIDTH are taken from the case file.

    python scripts/run_single_case.py                                   # input/message_case.txt (4 x 8)
    python scripts/run_single_case.py --case input/message_case_4x16.txt # 2 bytes per slot
    python scripts/run_single_case.py --case input/single_case.txt      # one slot per channel
    python scripts/run_single_case.py --sim xsim                        # Vivado XSIM instead of Icarus

Case file:
    NUM_CHANNELS = 4
    DATA_WIDTH   = 8                   bits per slot
    CH0 = 0123456789abcdef             message of device 0, hex without 0x
    CH1 = deadbeef   ...               messages may have different lengths

Writes to results/single_case/<case file name>/ (e.g. results/single_case/message_case/):
    rtl_result.txt      trace and received messages from tb_tdm_top_filebased.v
    golden_result.txt   the same, predicted by golden_model/single_case.py
    waveform.vcd        waveform of the RTL run (Icarus only; open it with GTKWave)

Then open rtl_result.txt and golden_result.txt next to each other (VS Code: select both
files > right click > Compare Selected; Notepad++ Compare plugin; WinMerge). Only the
"# source" line should differ.

Exit code: 0 = both files written, 2 = tool or input problem.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "golden_model"))

from run_tests import find_iverilog, find_vivado      # noqa: E402
import single_case                                     # noqa: E402

TB = ROOT / "techbench" / "tb_tdm_top_filebased.v"
TOP = "tb_tdm_top_filebased"
SRCS = sorted((ROOT / "src").glob("*.v"))


def plusargs(inp, out_dir):
    return {"CASE": inp, "TRACE": (out_dir / "rtl_result.txt").as_posix()}


def run_iverilog(tools, n, w, inp, out_dir):
    iverilog, vvp = tools
    build = ROOT / "sim"
    build.mkdir(exist_ok=True)
    exe = build / f"single_case_{n}x{w}.vvp"
    cmd = [iverilog, "-g2001", f"-P{TOP}.NUM_CHANNELS={n}", f"-P{TOP}.DATA_WIDTH={w}",
           "-o", str(exe), str(TB), *map(str, SRCS)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ERROR (iverilog):\n" + r.stdout + r.stderr)
    args = [f"+{k}={v}" for k, v in plusargs(inp, out_dir).items()]
    args.append(f"+VCD={(out_dir / 'waveform.vcd').as_posix()}")
    r = subprocess.run([vvp, str(exe), *args], capture_output=True, text=True)
    print("\n".join(l for l in r.stdout.splitlines() if "[filebased-tb]" in l or "TONG KET" in l))
    if r.returncode or "ERROR" in r.stdout:
        sys.exit(2)


def run_xsim(tools, n, w, inp, out_dir):
    xvlog, xelab, xsim = tools
    work = ROOT / "sim_xsim"
    work.mkdir(exist_ok=True)
    local = []
    for f in [TB, *SRCS]:
        text = f.read_text(encoding="utf-8", errors="replace")
        if "`timescale" not in text:
            text = "`timescale 1ns/1ps\n" + text
        (work / f.name).write_text(text, encoding="utf-8")
        local.append(f.name)
    snap = f"snap_single_{n}x{w}"
    steps = [[xvlog, "-sv", *local],
             [xelab, "-debug", "typical", "-generic_top", f"NUM_CHANNELS={n}",
              "-generic_top", f"DATA_WIDTH={w}", "-s", snap, f"work.{TOP}"],
             [xsim, snap, "-R", *[a for k, v in plusargs(inp, out_dir).items()
                                  for a in ("-testplusarg", f"{k}={v}")]]]
    for cmd in steps:
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
        if r.returncode or "ERROR" in r.stdout:
            sys.exit("ERROR (xsim):\n" + r.stdout + r.stderr)
    print("RTL result written:", out_dir / "rtl_result.txt")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", default=str(ROOT / "input" / "message_case.txt"), help="case file")
    ap.add_argument("--out-dir", help="output folder (default results/single_case/<case file name>)")
    ap.add_argument("--sim", choices=["iverilog", "xsim"], default="iverilog")
    a = ap.parse_args(argv)

    case = Path(a.case).resolve()
    if not case.exists():
        sys.exit(f"ERROR: case file {case} not found")
    n, w, _ = single_case.read_case(case)
    out_dir = Path(a.out_dir).resolve() if a.out_dir else ROOT / "results" / "single_case" / case.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Case: {n} channels x {w} bits, file {case}")
    if a.sim == "iverilog":
        tools = find_iverilog()
        if not tools:
            sys.exit("ERROR: Icarus Verilog not found (or use --sim xsim)")
        run_iverilog(tools, n, w, case.as_posix(), out_dir)
    else:
        tools = tuple(find_vivado(t) for t in ("xvlog", "xelab", "xsim"))
        if not all(tools):
            sys.exit("ERROR: Vivado xvlog/xelab/xsim not found (set VIVADO_BIN)")
        run_xsim(tools, n, w, case.as_posix(), out_dir)

    single_case.main(["--case", str(case), "--out", str(out_dir / "golden_result.txt")])
    print("\nOpen these two files side by side and compare them:")
    print("  ", out_dir / "rtl_result.txt")
    print("  ", out_dir / "golden_result.txt")


if __name__ == "__main__":
    main()
