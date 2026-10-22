r"""One command: simulate the RTL (Icarus Verilog or Vivado XSIM), then compare
with the Python golden model.

    python golden_model/run_verification.py                  # auto: iverilog, else xsim
    python golden_model/run_verification.py --sim xsim       # force Vivado XSIM
    python golden_model/run_verification.py --sim iverilog   # force Icarus Verilog
    python golden_model/run_verification.py --vectors input/random_vectors.hex
    python golden_model/run_verification.py --no-sim         # compare existing result files
    python golden_model/run_verification.py --no-sim --vectors D:/x/input_vectors.hex --results D:/x
                                                             # result files live in another folder
    python golden_model/run_verification.py --work D:/x      # same thing, short form for the Vivado GUI flow

Works from any directory. Exit code: 0 = PASS, 1 = FAIL, 2 = tool/sim problem.

XSIM is found on PATH or in the usual Vivado install folders (C:\Xilinx\Vivado\*,
C:\AMD\Vivado\*). Override with the environment variable VIVADO_BIN
(the folder that contains xvlog / xelab / xsim).
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import compare_output

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TB = ROOT / "techbench" / "tb_tdm_top_filebased.v"
SIM = ROOT / "sim_filebased"          # listed in .gitignore
XSIM_DIR = ROOT / "sim_xsim"          # scratch folder for XSIM, listed in .gitignore
TB_TOP = "tb_tdm_top_filebased"


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


def find_vivado_tool(name):
    """Locate xvlog / xelab / xsim (PATH, $VIVADO_BIN, then usual install folders)."""
    from shutil import which

    found = which(name)
    if found:
        return found

    exts = [".bat", ".exe", ""] if os.name == "nt" else [""]
    bins = []
    env = os.environ.get("VIVADO_BIN")
    if env:
        bins.append(Path(env))
    roots = []
    if os.name == "nt":
        for drive in "CDEF":
            for vendor in ("Xilinx", "AMD"):
                roots.append(Path(f"{drive}:/{vendor}/Vivado"))
    else:
        roots += [Path("/tools/Xilinx/Vivado"), Path("/opt/Xilinx/Vivado"),
                  Path("/opt/xilinx/Vivado"), Path("/tools/AMD/Vivado")]
    for root in roots:
        if root.is_dir():
            bins += [d / "bin" for d in sorted(root.iterdir(), reverse=True)]   # newest first
    for b in bins:
        for ext in exts:
            cand = b / (name + ext)
            if cand.exists():
                return str(cand)
    return None


def _show(r):
    print(r.stdout + r.stderr)


def _print_summary(stdout):
    for line in stdout.splitlines():
        if "FAIL" in line or "ERROR" in line or "TONG KET" in line or "loaded" in line:
            print("   ", line.strip())


def simulate_iverilog(vectors, paths):
    iverilog, vvp = find_tool("iverilog"), find_tool("vvp")
    if not iverilog or not vvp:
        print("ERROR: iverilog/vvp not found.")
        print("  Install Icarus Verilog and re-open the terminal, or use Vivado:")
        print("    python golden_model/run_verification.py --sim xsim")
        return False

    sources = [str(p) for p in sorted((ROOT / "src").glob("*.v"))]
    paths["hex"].parent.mkdir(parents=True, exist_ok=True)

    print("[1/2] compiling RTL + testbench (iverilog) ...")
    r = subprocess.run(
        [iverilog, "-g2012", "-o", str(SIM), str(TB), *sources],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.returncode != 0:
        _show(r)
        return False

    print("[2/2] running simulation (vvp) ...")
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
    _print_summary(r.stdout)
    if r.returncode != 0 or "ERROR" in r.stdout:
        _show(r)
        return False
    return True


def simulate_xsim(vectors, paths):
    xvlog, xelab, xsim = (find_vivado_tool(t) for t in ("xvlog", "xelab", "xsim"))
    if not (xvlog and xelab and xsim):
        print("ERROR: Vivado xvlog/xelab/xsim not found.")
        print("  Open 'Vivado <version> Tcl Shell' / run settings64.bat first, or set VIVADO_BIN")
        print("  to the folder that contains xvlog.bat, e.g.")
        print(r"    set VIVADO_BIN=C:\Xilinx\Vivado\2023.2\bin")
        return False

    paths["hex"].parent.mkdir(parents=True, exist_ok=True)
    XSIM_DIR.mkdir(exist_ok=True)

    # The RTL files carry no `timescale; give every file the testbench's 1ns/1ps
    # in a scratch copy so XSIM never mixes timescaled / un-timescaled files.
    # The repo files are not touched.
    #
    # File paths are written into the scratch copy of the testbench (its
    # parameters) instead of being passed with -testplusarg: xsim.bat is a
    # Windows batch wrapper and cmd.exe splits "NAME=C:/path" at '=' / ':',
    # which makes xsim fail with "Expected a switch but found C".
    param_paths = {"INPUT_FILE": vectors, "OUTPUT_FILE": paths["hex"],
                   "STREAM_FILE": paths["stream"], "LATENCY_FILE": paths["lat"]}
    files = [TB] + sorted((ROOT / "src").glob("*.v"))
    local = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if f == TB:
            for name, val in param_paths.items():
                text, n = re.subn(
                    r'(parameter\s+' + name + r'\s*=\s*)"[^"]*"',
                    lambda m, v=Path(val).as_posix(): m.group(1) + '"' + v + '"',
                    text,
                )
                if n != 1:
                    print(f"ERROR: could not patch parameter {name} in the testbench copy.")
                    return False
        if "`timescale" not in text:
            text = "`timescale 1ns/1ps\n" + text
        dst = XSIM_DIR / f.name
        dst.write_text(text, encoding="utf-8")
        local.append(dst.name)

    def run(cmd, label):
        print(label)
        r = subprocess.run(cmd, cwd=XSIM_DIR, capture_output=True, text=True)
        return r

    r = run([xvlog, "-sv", *local], "[1/3] compiling RTL + testbench (xvlog) ...")
    if r.returncode != 0 or "ERROR" in r.stdout:
        _show(r)
        return False

    r = run([xelab, "-debug", "off", "-s", "tdm_snap", f"work.{TB_TOP}"],
            "[2/3] elaborating (xelab) ...")
    if r.returncode != 0 or "ERROR" in r.stdout:
        _show(r)
        return False

    cmd = [xsim, "tdm_snap", "-R"]
    r = run(cmd, "[3/3] running simulation (xsim) ...")
    _print_summary(r.stdout)
    if r.returncode != 0 or "[filebased-tb] ERROR" in r.stdout:
        _show(r)
        return False
    if "TONG KET" not in r.stdout:
        print("ERROR: simulation did not reach the end of the testbench (no TONG KET line).")
        _show(r)
        return False
    return True


def simulate(vectors, paths, which="auto"):
    if which == "iverilog":
        return simulate_iverilog(vectors, paths)
    if which == "xsim":
        return simulate_xsim(vectors, paths)
    # auto
    if find_tool("iverilog") and find_tool("vvp"):
        return simulate_iverilog(vectors, paths)
    if find_vivado_tool("xsim"):
        print("iverilog not found - using Vivado XSIM.")
        return simulate_xsim(vectors, paths)
    print("ERROR: no simulator found (iverilog or Vivado xsim).")
    print("  Vivado users: set VIVADO_BIN to the Vivado 'bin' folder, then run with --sim xsim.")
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().split("\n")[0])
    ap.add_argument("--vectors", default=str(compare_output.DEFAULT_INPUT))
    ap.add_argument("--sim", choices=["auto", "iverilog", "xsim"], default="auto",
                    help="simulator to use (default: iverilog if installed, else Vivado xsim)")
    ap.add_argument("--results", metavar="DIR",
                    help="folder that holds (or will receive) rtl_output_*.hex, rtl_stream_*.txt, "
                         "rtl_latency_*.txt and the report; default: golden_model/verification_logs. "
                         "Use it when Vivado wrote the files outside the repository.")
    ap.add_argument("--work", nargs="?", const="", metavar="DIR",
                    help="shortcut for the Vivado GUI flow: same as --no-sim --vectors DIR/input_vectors.hex "
                         "--results DIR. Without DIR it uses $TDM_WORK, else ~/TDM/verify")
    ap.add_argument("--no-excel", action="store_true",
                    help="do not write verification_results.xlsx (needs openpyxl)")
    ap.add_argument("--sim-label", default=None, metavar="TEXT",
                    help='text for the "Simulator / tool" cell in the Excel file, e.g. "Vivado 2020.2 XSIM"')
    ap.add_argument("--no-sim", action="store_true",
                    help="skip the simulation, only compare existing result files")
    args = ap.parse_args(argv)

    if args.work is not None:
        work = Path(args.work or os.environ.get("TDM_WORK") or Path.home() / "TDM" / "verify")
        args.no_sim = True
        args.results = str(work)
        args.vectors = str(work / "input_vectors.hex")
        print(f"Vivado GUI flow: comparing the files in {work}")

    vectors = Path(args.vectors).resolve()
    if not vectors.exists():
        print(f"ERROR: input file not found: {vectors}")
        return 2

    paths = compare_output.default_paths(vectors)
    if args.results:
        res = Path(args.results).resolve()
        res.mkdir(parents=True, exist_ok=True)
        paths = {k: res / v.name for k, v in paths.items()}

    if not args.no_sim and not simulate(vectors, paths, args.sim):
        return 2

    if args.sim_label:
        label = args.sim_label
    elif args.work is not None:
        label = "Vivado XSIM (GUI run)"
    elif args.no_sim:
        label = "external simulation (result files supplied)"
    else:
        label = {"iverilog": "Icarus Verilog", "xsim": "Vivado XSIM"}.get(args.sim, "auto-detected simulator")

    ok = compare_output.run_comparison(
        vectors, paths["hex"], paths["stream"], paths["lat"], paths["report"],
        excel_file=None if args.no_excel else paths["xlsx"], simulator=label,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
