r"""Run the self-checking system testbench of the project with one command.

    python scripts/run_tests.py                 # Icarus Verilog if installed, else Vivado XSIM
    python scripts/run_tests.py --sim iverilog
    python scripts/run_tests.py --sim xsim
    python scripts/run_tests.py tb_tdm_top      # only the testbenches whose name contains this text
    python scripts/run_tests.py -v              # also print every [PASS]/[FAIL] line

Each techbench/tb_*.v is compiled together with src/*.v, simulated to $finish, and judged by its
[PASS] / [FAIL] lines. tb_tdm_top_filebased.v is NOT part of this suite: it needs input files and
is driven by golden_model/run_verification.py.

Works from any directory. Waveform files (.vcd) and build products go to sim/ (git-ignored).
Exit code: 0 = every testbench passed, 1 = at least one failed, 2 = no simulator / compile problem.
For Vivado XSIM the project path must not contain accents or other non-ASCII characters.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from shutil import which

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TB_DIR = ROOT / "techbench"
BUILD = ROOT / "sim"
XSIM_DIR = ROOT / "sim_xsim"
SKIP = {"tb_tdm_top_filebased"}          # driven by golden_model/run_verification.py
ORDER = ["tb_tdm_top"]


def find_iverilog():
    iv, vvp = which("iverilog"), which("vvp")
    if iv and vvp:
        return iv, vvp
    exe = ".exe" if os.name == "nt" else ""
    for base in (r"C:\iverilog\bin", r"C:\Program Files\iverilog\bin", "/usr/local/bin", "/usr/bin"):
        a, b = Path(base) / f"iverilog{exe}", Path(base) / f"vvp{exe}"
        if a.exists() and b.exists():
            return str(a), str(b)
    return None


def find_vivado(name):
    found = which(name)
    if found:
        return found
    exts = [".bat", ".exe", ""] if os.name == "nt" else [""]
    bins = []
    if os.environ.get("VIVADO_BIN"):
        bins.append(Path(os.environ["VIVADO_BIN"]))
    roots = []
    if os.name == "nt":
        roots = [Path(f"{d}:/{v}/Vivado") for d in "CDEF" for v in ("Xilinx", "AMD")]
    else:
        roots = [Path(p) for p in ("/tools/Xilinx/Vivado", "/opt/Xilinx/Vivado", "/tools/AMD/Vivado")]
    for r in roots:
        if r.is_dir():
            bins += [d / "bin" for d in sorted(r.iterdir(), reverse=True)]
    for b in bins:
        for e in exts:
            if (b / (name + e)).exists():
                return str(b / (name + e))
    return None


def testbenches(filters):
    found = {p.stem: p for p in TB_DIR.glob("tb_*.v") if p.stem not in SKIP}
    names = [n for n in ORDER if n in found] + sorted(n for n in found if n not in ORDER)
    if filters:
        names = [n for n in names if any(f in n for f in filters)]
    return [(n, found[n]) for n in names]


def run_iverilog(tools, name, tb, srcs):
    iverilog, vvp = tools
    BUILD.mkdir(exist_ok=True)
    out = BUILD / f"{name}.vvp"
    r = subprocess.run([iverilog, "-g2012", "-o", str(out), str(tb), *map(str, srcs)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stdout + r.stderr
    r = subprocess.run([vvp, str(out)], cwd=BUILD, capture_output=True, text=True)
    return r.stdout, r.stdout + r.stderr if r.returncode else ""


def run_xsim(tools, name, tb, srcs):
    xvlog, xelab, xsim = tools
    XSIM_DIR.mkdir(exist_ok=True)
    local = []
    for f in [tb, *srcs]:
        text = f.read_text(encoding="utf-8", errors="replace")
        if "`timescale" not in text:
            text = "`timescale 1ns/1ps\n" + text
        dst = XSIM_DIR / f.name
        dst.write_text(text, encoding="utf-8")
        local.append(dst.name)
    snap = f"snap_{name}"
    for cmd in ([xvlog, "-sv", *local], [xelab, "-debug", "off", "-s", snap, f"work.{name}"]):
        r = subprocess.run(cmd, cwd=XSIM_DIR, capture_output=True, text=True)
        if r.returncode != 0 or "ERROR" in r.stdout:
            return None, r.stdout + r.stderr
    r = subprocess.run([xsim, snap, "-R"], cwd=XSIM_DIR, capture_output=True, text=True)
    return r.stdout, r.stdout + r.stderr if r.returncode else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    ap.add_argument("filters", nargs="*", help="only run testbenches whose name contains one of these")
    ap.add_argument("--sim", choices=["auto", "iverilog", "xsim"], default="auto")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every [PASS]/[FAIL] line")
    args = ap.parse_args(argv)

    sim = args.sim
    iv = find_iverilog() if sim in ("auto", "iverilog") else None
    xs = None
    if sim == "xsim" or (sim == "auto" and not iv):
        xs = tuple(find_vivado(t) for t in ("xvlog", "xelab", "xsim"))
        if not all(xs):
            xs = None
    if sim == "iverilog" and not iv or sim == "xsim" and not xs or (not iv and not xs):
        print("ERROR: no simulator found. Install Icarus Verilog (iverilog, vvp) or Vivado "
              "(set VIVADO_BIN to its bin folder).")
        return 2

    runner, tools, label = (run_iverilog, iv, "Icarus Verilog") if iv else (run_xsim, xs, "Vivado XSIM")
    srcs = sorted(SRC.glob("*.v"))
    benches = testbenches(args.filters)
    if not benches:
        print("No testbench matches.")
        return 2

    print(f"Simulator: {label}   |   {len(benches)} testbench(es), {len(srcs)} RTL files\n")
    print(f"{'testbench':<28}{'checks':>8}{'passed':>8}{'failed':>8}   result")
    print("-" * 64)
    total_p = total_f = 0
    bad = False
    compile_error = False
    for name, tb in benches:
        out, err = runner(tools, name, tb, srcs)
        if out is None:
            print(f"{name:<28}{'':>24}   COMPILE ERROR")
            print(err)
            compile_error = True
            continue
        passed = len(re.findall(r"\[PASS\]", out))
        failed = len(re.findall(r"\[FAIL\]", out))
        ok = failed == 0 and passed > 0 and not err
        total_p += passed
        total_f += failed
        bad |= not ok
        print(f"{name:<28}{passed + failed:>8}{passed:>8}{failed:>8}   {'PASS' if ok else 'FAIL'}")
        if args.verbose or not ok:
            for line in out.splitlines():
                if "[FAIL]" in line or (args.verbose and "[PASS]" in line):
                    print("      " + line.strip())
            if err:
                print(err)
    print("-" * 64)
    print(f"{'TOTAL':<28}{total_p + total_f:>8}{total_p:>8}{total_f:>8}   "
          f"{'ALL PASSED' if not bad and not compile_error else 'FAILED'}")
    if compile_error:
        return 2
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
