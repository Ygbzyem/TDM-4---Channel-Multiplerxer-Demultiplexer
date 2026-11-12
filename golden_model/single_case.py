r"""Golden-model result for ONE case written in a small text file, in the same text
format as the trace written by techbench/tb_tdm_top_filebased.v (CASE_FILE / TRACE_FILE),
so the two files can be opened side by side and compared by eye.

    python golden_model/single_case.py                                        # input/single_case.txt
    python golden_model/single_case.py --case input/single_case_4x16.txt --out golden_result.txt

Case file (the same file the RTL testbench reads):
    NUM_CHANNELS = 4
    DATA_WIDTH   = 8
    CH0 = a5          hex without 0x, one line per channel
    CH1 = 3c
    ...
// comments and blank lines are ignored. This script reads no RTL result and
compares nothing.
"""

import argparse
import re
import sys
from pathlib import Path

from golden_model import TDMGoldenModel

ROOT = Path(__file__).resolve().parent.parent


def read_case(path):
    """Return (num_channels, data_width, [CH0, CH1, ...]) from a case file."""
    n = w = None
    chans = {}
    for no, raw in enumerate(Path(path).read_text().splitlines(), 1):
        line = raw.split("//")[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"(NUM_CHANNELS|DATA_WIDTH|CH(\d+))\s*=\s*(\S+)", line)
        if not m:
            sys.exit(f"ERROR: {path}:{no}: cannot read '{raw.strip()}'")
        key, idx, val = m.group(1), m.group(2), m.group(3)
        if key == "NUM_CHANNELS":
            n = int(val)
        elif key == "DATA_WIDTH":
            w = int(val)
        else:
            if val.lower().startswith("0x"):
                sys.exit(f"ERROR: {path}:{no}: write the value without 0x (the RTL testbench reads plain hex)")
            chans[int(idx)] = int(val, 16)
    if n is None or w is None:
        sys.exit(f"ERROR: {path} must set NUM_CHANNELS and DATA_WIDTH")
    for i in range(n):
        if i not in chans:
            sys.exit(f"ERROR: {path}: line CH{i} = ... is missing")
        if chans[i] >> w:
            sys.exit(f"ERROR: {path}: CH{i} = {chans[i]:x} is wider than DATA_WIDTH = {w} bits")
    extra = [i for i in chans if i >= n]
    if extra:
        sys.exit(f"ERROR: {path}: CH{extra[0]} does not exist (NUM_CHANNELS = {n})")
    return n, w, [chans[i] for i in range(n)]


def write_result(gm, values, out_path, clk_period=10):
    n, w = gm.num_channels, gm.data_width
    hx = lambda v: format(v, f"0{(w + 3) // 4}x")
    vector = 0
    for v in values:
        vector = (vector << w) | v                      # {CH0, CH1, ...}
    lines = [
        "# TDM single-case result",
        "# source       : golden model (Python)",
        f"# NUM_CHANNELS : {n}",
        f"# DATA_WIDTH   : {w}",
        f"# frame length : {gm.frame_cycles} cycles",
        f"# clock period : {clk_period} ns",
        "# cycle 0      : first clock cycle after reset is released",
        "#",
        "# [1] inputs, one line per channel, and the packed vector {CH0, CH1, ...}",
    ]
    lines += [f"CH{i} = {hx(v)}" for i, v in enumerate(values)]
    lines.append(f"vector = {format(vector, f'0{(n * w + 3) // 4}x')}")
    lines += [
        "#",
        "# [2] cycle-by-cycle trace: ch / bit = channel and bit number on TDM_DATA (MSB first)",
        "# cycle  time_ns  ch  bit  TDM_DATA  | outputs during this cycle",
    ]
    for r in gm.timeline(values, cycles=gm.frame_cycles + 2):
        outs = "".join(f" CH{i}={hx(v)}" for i, v in enumerate(r["outputs"]))
        lines.append(f"{r['cycle']:7d} {r['cycle'] * clk_period:8d} {r['ch']:3d} "
                     f"{r['bit']:4d} {r['tdm_data']:9d}  |{outs}")
    words = gm.run_frame(*values)["outputs"]
    lines += ["#", "# [3] output update: first cycle in which CHi_OUT holds the received value"]
    for i in range(n):
        c = gm.valid_cycle(i)
        lines.append(f"CH{i}_OUT = {hx(words[i])}  from cycle {c} ({c * clk_period} ns)")
    lat = gm.cold_start_latency()
    lines.append(f"# cold-start latency: {lat} cycles ({lat * clk_period} ns)")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", default=str(ROOT / "input" / "single_case.txt"), help="case file")
    ap.add_argument("--out", default="golden_result.txt")
    ap.add_argument("--clk-period", type=int, default=10, help="clock period in ns (default 10)")
    a = ap.parse_args(argv)

    n, w, values = read_case(a.case)
    gm = TDMGoldenModel(n, w)
    write_result(gm, values, a.out, a.clk_period)
    print(f"Golden result written: {a.out} ({n} channels x {w} bits, {gm.frame_cycles + 2} cycles)")


if __name__ == "__main__":
    main()
