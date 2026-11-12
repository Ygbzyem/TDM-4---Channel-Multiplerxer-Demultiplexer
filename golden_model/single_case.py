r"""Golden-model result for ONE case written in a small text file, in the same text
format as the trace written by techbench/tb_tdm_top_filebased.v (CASE_FILE / TRACE_FILE),
so the two files can be opened side by side and compared by eye.

    python golden_model/single_case.py                                        # input/message_case.txt
    python golden_model/single_case.py --case input/message_case_4x16.txt --out golden_result.txt

Case file (the same file the RTL testbench reads):
    NUM_CHANNELS = 4
    DATA_WIDTH   = 8                  bits per time slot
    CH0 = 0123456789abcdef            whole message of device 0, hex without 0x
    CH1 = deadbeef                    messages may have different lengths
    ...
Each message is cut into DATA_WIDTH-bit slots; frame f carries slot f of every
channel (CH0 first) and a finished channel sends 0.
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
    """Return (num_channels, data_width, [message of CH0, CH1, ...]) from a case file.
    Each message is a string of hex digits."""
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
            if not re.fullmatch(r"[0-9a-fA-F]+", val):
                sys.exit(f"ERROR: {path}:{no}: message must be hex digits only (no 0x)")
            chans[int(idx)] = val.lower()
    if n is None or w is None:
        sys.exit(f"ERROR: {path} must set NUM_CHANNELS and DATA_WIDTH")
    for i in range(n):
        if i not in chans:
            sys.exit(f"ERROR: {path}: line CH{i} = ... is missing")
    extra = [i for i in chans if i >= n]
    if extra:
        sys.exit(f"ERROR: {path}: CH{extra[0]} does not exist (NUM_CHANNELS = {n})")
    return n, w, [chans[i] for i in range(n)]


def write_result(gm, messages, out_path, clk_period=10):
    n, w, fc = gm.num_channels, gm.data_width, gm.frame_cycles
    hx = lambda v: format(v, f"0{(w + 3) // 4}x")
    slots = [gm.message_slots(m) for m in messages]           # testbench: read_message_case
    frames = gm.frames(slots)                                 # testbench: apply_frame
    last = len(frames) * fc + 1                               # last word reaches its output
    lines = [
        "# TDM single-case result",
        "# source       : golden model (Python)",
        f"# NUM_CHANNELS : {n}",
        f"# DATA_WIDTH   : {w} bits per slot",
        f"# frame length : {fc} cycles (one slot of every channel)",
        f"# frames       : {len(frames)}",
        f"# clock period : {clk_period} ns",
        "# cycle 0      : first clock cycle after reset is released",
        "#",
        "# [1] messages and their slots (a finished channel sends 0)",
    ]
    lines += [f"CH{c} = {messages[c]}  slots:" + "".join(f" {hx(v)}" for v in slots[c]) for c in range(n)]
    lines += [
        "#",
        "# [2] cycle-by-cycle trace: ch / bit = channel and bit number on TDM_DATA (MSB first)",
        "# cycle  time_ns  frame  ch  bit  TDM_DATA  | outputs during this cycle",
    ]
    for r in gm.timeline_frames(frames, cycles=last + 1):
        outs = "".join(f" CH{c}={hx(v)}" for c, v in enumerate(r["outputs"]))
        lines.append(f"{r['cycle']:7d} {r['cycle'] * clk_period:8d} {r['frame']:6d} {r['ch']:3d} "
                     f"{r['bit']:4d} {r['tdm_data']:9d}  |{outs}")
    lines += ["#", "# [3] received slots per channel: value(cycle in which the output took it), rebuilt message"]
    for c in range(n):
        got = "".join(f" {hx(frames[f][c])}({gm.valid_cycle(c, f)})" for f in range(len(frames)))
        lines.append(f"CH{c}_OUT :{got}")
    for c in range(n):
        received = [frames[f][c] for f in range(len(frames))]
        lines.append(f"CH{c} message = {gm.rebuild_message(received, len(messages[c]))}")
    lines.append(f"# last output update: cycle {last} ({last * clk_period} ns)")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", default=str(ROOT / "input" / "message_case.txt"), help="case file")
    ap.add_argument("--out", default="golden_result.txt")
    ap.add_argument("--clk-period", type=int, default=10, help="clock period in ns (default 10)")
    a = ap.parse_args(argv)

    n, w, messages = read_case(a.case)
    gm = TDMGoldenModel(n, w)
    write_result(gm, messages, a.out, a.clk_period)
    print(f"Golden result written: {a.out} ({n} channels x {w} bits per slot)")


if __name__ == "__main__":
    main()
