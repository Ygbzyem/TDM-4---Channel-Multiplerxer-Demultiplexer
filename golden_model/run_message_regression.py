r"""Regression in message mode: many cases through the RTL and the golden model.

Every case is the same kind of file as input/input_vectors.txt: NUM_CHANNELS,
DATA_WIDTH and one whole message (hex) per device. The messages are cut into
DATA_WIDTH-bit slots, frame f carries slot f of every channel and a finished
channel sends 0. For each case this script

  1. runs techbench/tb_tdm_top_filebased.v (RUN_CASE = 1) -> RTL result file,
  2. runs the golden model (golden_model.write_result)    -> golden result file,
  3. compares the two files line by line (only the "# source" line may differ)
     and reads the self-check of the testbench (TONG KET ... loi).

    python golden_model/run_message_regression.py                 # cases of input/test_cases.txt
                                                                   # + 20 random 4 x 8 cases
    python golden_model/run_message_regression.py --sizes 4x8,4x16,8x8,3x12 --random 25
    python golden_model/run_message_regression.py --no-cases --random 50 --seed 7
    python golden_model/run_message_regression.py --sim xsim      # Vivado XSIM instead of Icarus

Outputs (golden_model/verification_logs/):
    message_cases/<case>.txt, <case>_rtl.txt, <case>_golden.txt   every case and both results
    message_report.md                                             one line per case
    message_results.xlsx                                          same, as a workbook (needs openpyxl)

Works from any directory. Exit code: 0 = every case PASS, 1 = a case failed, 2 = tool problem.
"""

import argparse
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import golden_model as gmod
from run_verification import find_tool, find_vivado_tool

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TB = ROOT / "techbench" / "tb_tdm_top_filebased.v"
TB_TOP = "tb_tdm_top_filebased"
LOGS = HERE / "verification_logs"
CASE_DIR = LOGS / "message_cases"
BUILD = ROOT / "sim_message"          # git-ignored scratch folder
MAX_HEX = 512                         # testbench: hex digits per message
MAX_SLOTS = 256                       # testbench: slots per channel


# ---------------------------------------------------------------- cases
def case_text(n, w, messages, title=""):
    lines = [f"// {title}"] if title else []
    lines += [f"NUM_CHANNELS = {n}", f"DATA_WIDTH   = {w}"]
    lines += [f"CH{i} = {m}" for i, m in enumerate(messages)]
    return "\n".join(lines) + "\n"


def cases_from_library(path):
    """Split input/test_cases.txt into cases: a case ends with its last CH line."""
    cases, cur = [], []
    for raw in Path(path).read_text().splitlines():
        line = raw.split("//")[0].strip()
        if not line:
            continue
        if line.startswith("NUM_CHANNELS") and cur:
            cases.append(cur)
            cur = []
        cur.append(line)
    if cur:
        cases.append(cur)
    out = []
    for k, lines in enumerate(cases, 1):
        tmp = CASE_DIR / f"_parse_{k}.txt"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text("\n".join(lines) + "\n")
        n, w, msgs = gmod.read_case(tmp)
        tmp.unlink()
        out.append((f"case{k}", n, w, msgs, f"input/test_cases.txt, case {k}"))
    return out


def random_cases(sizes, count, seed, max_digits):
    rng = random.Random(seed)
    out = []
    for n, w in sizes:
        for k in range(count):
            msgs = ["".join(rng.choice("0123456789abcdef") for _ in range(rng.randint(1, max_digits)))
                    for _ in range(n)]
            out.append((f"rand_{n}x{w}_{k:03d}", n, w, msgs, f"random, seed {seed}"))
    return out


def parse_sizes(text):
    sizes = []
    for item in text.split(","):
        m = re.fullmatch(r"\s*(\d+)\s*x\s*(\d+)\s*", item)
        if not m:
            raise SystemExit(f"--sizes: cannot read '{item}', use e.g. 4x8,4x16")
        n, w = int(m.group(1)), int(m.group(2))
        if n < 2 or w < 2:
            raise SystemExit("--sizes: NUM_CHANNELS and DATA_WIDTH must both be at least 2")
        sizes.append((n, w))
    return sizes


# ---------------------------------------------------------------- simulators
class Icarus:
    name = "Icarus Verilog"

    def __init__(self):
        self.iverilog, self.vvp = find_tool("iverilog"), find_tool("vvp")
        self.ok = bool(self.iverilog and self.vvp)

    def build(self, n, w):
        BUILD.mkdir(exist_ok=True)
        out = BUILD / f"tb_{n}x{w}.vvp"
        src = [str(p) for p in sorted((ROOT / "src").glob("*.v"))]
        r = subprocess.run([self.iverilog, "-g2001", f"-P{TB_TOP}.NUM_CHANNELS={n}",
                            f"-P{TB_TOP}.DATA_WIDTH={w}", "-o", str(out), str(TB), *src],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout + r.stderr)
            return None
        return out

    def run(self, snap, case_file, rtl_file):
        r = subprocess.run([self.vvp, str(snap), f"+CASE={case_file}", f"+TRACE={rtl_file}"],
                           cwd=ROOT, capture_output=True, text=True)
        return r.stdout + r.stderr


class XSim:
    """Vivado XSIM. No plusargs (xsim.bat on Windows splits NAME=C:/path): every size gets a
    scratch folder with input/input_vectors.txt and results/; the testbench (REPO_DIR = ".")
    finds input/input_vectors.txt in its run folder."""
    name = "Vivado XSIM"

    def __init__(self):
        self.tools = [find_vivado_tool(t) for t in ("xvlog", "xelab", "xsim")]
        self.ok = all(self.tools)

    def build(self, n, w):
        xvlog, xelab, _ = self.tools
        d = BUILD / f"xsim_{n}x{w}"
        (d / "input").mkdir(parents=True, exist_ok=True)
        (d / "results").mkdir(exist_ok=True)
        local = []
        for f in [TB] + sorted((ROOT / "src").glob("*.v")):
            text = f.read_text(encoding="utf-8", errors="replace")
            if f == TB:
                for pname, val in (("NUM_CHANNELS", n), ("DATA_WIDTH", w)):
                    text, k = re.subn(r"(parameter\s+" + pname + r"\s*=\s*)\d+", r"\g<1>" + str(val), text, count=1)
                    if k != 1:
                        print(f"ERROR: could not set {pname} in the testbench copy")
                        return None
                text, k = re.subn(r'(parameter\s+REPO_DIR\s*=\s*)"[^"]*"', r'\g<1>"."', text, count=1)
                if k != 1:
                    print("ERROR: could not set REPO_DIR in the testbench copy")
                    return None
            if "`timescale" not in text:
                text = "`timescale 1ns/1ps\n" + text
            (d / f.name).write_text(text, encoding="utf-8")
            local.append(f.name)
        for cmd in ([xvlog, "-sv", *local], [xelab, "-debug", "off", "-s", "tdm_msg", f"work.{TB_TOP}"]):
            r = subprocess.run(cmd, cwd=d, capture_output=True, text=True)
            if r.returncode != 0 or "ERROR" in r.stdout:
                print(r.stdout + r.stderr)
                return None
        return d

    def run(self, d, case_file, rtl_file):
        shutil.copyfile(case_file, d / "input" / "input_vectors.txt")
        res = d / "results" / "rtl_result.txt"
        if res.exists():
            res.unlink()
        r = subprocess.run([self.tools[2], "tdm_msg", "-R"], cwd=d, capture_output=True, text=True)
        if res.exists():
            shutil.copyfile(res, rtl_file)
        return r.stdout + r.stderr


def pick_sim(which):
    if which in ("auto", "iverilog"):
        s = Icarus()
        if s.ok:
            return s
        if which == "iverilog":
            print("ERROR: iverilog/vvp not found.")
            return None
    s = XSim()
    if s.ok:
        if which == "auto":
            print("iverilog not found - using Vivado XSIM.")
        return s
    print("ERROR: no simulator found (iverilog, or Vivado xvlog/xelab/xsim; set VIVADO_BIN).")
    return None


# ---------------------------------------------------------------- compare
def compare_files(rtl_file, golden_file):
    """(ok, text of the first difference); the '# source' line is skipped."""
    if not Path(rtl_file).exists():
        return False, "no RTL result file"
    keep = lambda p: [l.rstrip() for l in Path(p).read_text().splitlines() if not l.startswith("# source")]
    a, b = keep(rtl_file), keep(golden_file)
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else "<end of file>"
        y = b[i] if i < len(b) else "<end of file>"
        if x != y:
            return False, f"first difference: rtl '{x}' / golden '{y}'"
    return True, ""


def tb_errors(log):
    m = re.search(r"TONG KET:\s*(\d+)\s*kenh,\s*(\d+)\s*loi", log)
    return int(m.group(2)) if m else None


# ---------------------------------------------------------------- reports
def write_report(path, rows, sim_name):
    passed = sum(r["ok"] for r in rows)
    lines = ["# Message-mode regression report", "",
             f"Generated : {datetime.now():%Y-%m-%d %H:%M:%S}  ",
             f"Simulator : {sim_name}  ",
             "Reference : Python golden model (`golden_model.write_result`)", "",
             f"Cases: {len(rows)}, passed: {passed}, failed: {len(rows) - passed}", "",
             "Each case: messages cut into DATA_WIDTH-bit slots, frame f = slot f of every channel, a finished "
             "channel sends 0. PASS = the RTL result file equals the golden result file (except the '# source' "
             "line) and the testbench self-check reports 0 errors.", "",
             "| # | Case | Size | Frames | Last output (cycle) | Messages | TB errors | Files equal | Result |",
             "|---|------|------|--------|---------------------|----------|-----------|-------------|--------|"]
    for i, r in enumerate(rows):
        msgs = ", ".join(r["messages"])
        if len(msgs) > 60:
            msgs = msgs[:57] + "..."
        lines.append(f"| {i} | {r['name']} | {r['n']} x {r['w']} | {r['frames']} | {r['last']} | `{msgs}` | "
                     f"{'-' if r['tb_err'] is None else r['tb_err']} | {'yes' if r['same'] else 'no'} | "
                     f"{'PASS' if r['ok'] else 'FAIL'} |")
    fails = [r for r in rows if not r["ok"]]
    if fails:
        lines += ["", "## Failures", ""]
        lines += [f"- {r['name']}: {r['why']}" for r in fails]
    lines += ["", f"Status: {'PASS' if not fails else 'FAIL'}", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_excel(path, rows, sim_name):
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Message cases"
    heads = [("#", 5), ("Case", 18), ("Source", 26), ("NUM_CHANNELS", 9), ("DATA_WIDTH", 9),
             ("Frames", 8), ("Frame length (cycles)", 11), ("Last output (cycle)", 11),
             ("Messages (CH0, CH1, ...)", 60), ("TB errors", 9), ("Files equal", 10),
             ("First difference", 50), ("Result", 9)]
    head_font, head_fill = Font(name="Arial", bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3A5F")
    for c, (h, wdt) in enumerate(heads, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font, cell.fill = head_font, head_fill
        cell.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
        ws.column_dimensions[cell.column_letter].width = wdt
    for i, r in enumerate(rows):
        row = i + 2
        vals = [i, r["name"], r["source"], r["n"], r["w"], r["frames"], f"=D{row}*E{row}", r["last"],
                ", ".join(r["messages"]), r["tb_err"], "yes" if r["same"] else "no", r["why"],
                f'=IF(AND(J{row}=0,K{row}="yes"),"PASS","FAIL")']
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=row, column=c, value=v)
            cell.font = Font(name="Consolas" if c == 9 else "Arial", size=10)
    last = len(rows) + 1
    ws.cell(row=last + 2, column=2, value="Cases").font = Font(name="Arial", bold=True)
    ws.cell(row=last + 2, column=3, value=f"=COUNTA(B2:B{last})")
    ws.cell(row=last + 3, column=2, value="Passed").font = Font(name="Arial", bold=True)
    ws.cell(row=last + 3, column=3, value=f'=COUNTIF(M2:M{last},"PASS")')
    ws.cell(row=last + 4, column=2, value="Simulator").font = Font(name="Arial", bold=True)
    ws.cell(row=last + 4, column=3, value=sim_name)
    ws.cell(row=last + 5, column=2, value="Generated").font = Font(name="Arial", bold=True)
    ws.cell(row=last + 5, column=3, value=f"{datetime.now():%Y-%m-%d %H:%M:%S}")
    ok = dict(font=Font(bold=True, color="006100"), fill=PatternFill("solid", bgColor="C6EFCE"))
    bad = dict(font=Font(bold=True, color="9C0006"), fill=PatternFill("solid", bgColor="FFC7CE"))
    ws.conditional_formatting.add(f"M2:M{last}", CellIsRule(operator="equal", formula=['"PASS"'], **ok))
    ws.conditional_formatting.add(f"M2:M{last}", CellIsRule(operator="equal", formula=['"FAIL"'], **bad))
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:M{last}"
    wb.save(path)


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().split("\n")[0])
    ap.add_argument("--cases", default=str(ROOT / "input" / "test_cases.txt"),
                    help="library of cases to run first (default input/test_cases.txt)")
    ap.add_argument("--no-cases", action="store_true", help="skip the library, random cases only")
    ap.add_argument("--sizes", default="4x8", help="sizes of the random cases, e.g. 4x8,4x16,8x8 (default 4x8)")
    ap.add_argument("--random", type=int, default=20, help="random cases per size (default 20, 0 = none)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-digits", type=int, default=24, help="longest random message in hex digits (default 24)")
    ap.add_argument("--sim", choices=["auto", "iverilog", "xsim"], default="auto")
    ap.add_argument("--no-excel", action="store_true")
    a = ap.parse_args(argv)

    if not 1 <= a.max_digits <= MAX_HEX:
        print(f"ERROR: --max-digits must be 1..{MAX_HEX}")
        return 2
    cases = [] if a.no_cases else cases_from_library(a.cases)
    cases += random_cases(parse_sizes(a.sizes), a.random, a.seed, a.max_digits)
    if not cases:
        print("ERROR: no case to run")
        return 2
    sim = pick_sim(a.sim)
    if sim is None:
        return 2

    CASE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Message-mode regression: {len(cases)} case(s), simulator: {sim.name}")
    snaps, rows = {}, []
    for name, n, w, msgs, source in cases:
        gm = gmod.TDMGoldenModel(n, w)
        slots = [gm.message_slots(m) for m in msgs]
        if max(len(s) for s in slots) > MAX_SLOTS or max(len(m) for m in msgs) > MAX_HEX:
            print(f"[SKIP] {name}: longer than the testbench limits (MAX_SLOTS {MAX_SLOTS}, MAX_HEX {MAX_HEX})")
            continue
        if (n, w) not in snaps:
            print(f"  building the testbench for {n} x {w} ...")
            snaps[(n, w)] = sim.build(n, w)
        if snaps[(n, w)] is None:
            print(f"ERROR: could not build the testbench for {n} x {w}")
            return 2
        case_file = CASE_DIR / f"{name}.txt"
        rtl_file, gold_file = CASE_DIR / f"{name}_rtl.txt", CASE_DIR / f"{name}_golden.txt"
        case_file.write_text(case_text(n, w, msgs, f"{name}: {source}"))
        for f in (rtl_file, gold_file):
            if f.exists():
                f.unlink()

        log = sim.run(snaps[(n, w)], case_file, rtl_file)               # 1) RTL
        gmod.write_result(gm, msgs, gold_file, verbose=False)            # 2) golden model
        same, why = compare_files(rtl_file, gold_file)                   # 3) compare
        err = tb_errors(log)
        if err is None and not why:
            why = "testbench did not reach TONG KET: " + " | ".join(log.strip().splitlines()[-3:])
        elif err:
            why = (why + "; " if why else "") + f"testbench self-check: {err} error(s)"
        frames = len(gm.frames(slots))
        row = {"name": name, "source": source, "n": n, "w": w, "messages": msgs, "frames": frames,
               "last": frames * gm.frame_cycles + 1, "tb_err": err, "same": same,
               "ok": same and err == 0, "why": why}
        rows.append(row)
        print(f"[{'PASS' if row['ok'] else 'FAIL'}] {name:<16} {n} x {w:<3} frames {frames:<3} "
              f"{', '.join(msgs)[:60]}" + ("" if row["ok"] else f"\n        {why}"))

    passed = sum(r["ok"] for r in rows)
    report = LOGS / "message_report.md"
    write_report(report, rows, sim.name)
    print("=" * 62)
    print(f" cases passed : {passed}/{len(rows)}")
    print(">>> ALL MESSAGE CASES PASSED" if passed == len(rows) else ">>> MESSAGE REGRESSION FAILED")
    print(f"Report written: {report}")
    if not a.no_excel:
        try:
            xl = LOGS / "message_results.xlsx"
            write_excel(xl, rows, sim.name)
            print(f"Excel written : {xl}")
        except ImportError:
            print("Excel skipped : openpyxl is not installed  ->  python -m pip install openpyxl")
        except PermissionError:
            print("Excel FAILED  : message_results.xlsx is open in Excel - close it and run again")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
