# Golden model — how to run it

The **golden model** is a tiny Python program that knows what the TDM system *should* do.
It never looks at the Verilog. The RTL simulation (Vivado XSIM or Icarus) writes its results
to files, and the Python scripts in this folder compare those files with what the golden
model predicts.

```
 input/input_vectors.hex ──► RTL simulation ──► golden_model/verification_logs/rtl_*.{hex,txt}
        │                    (Vivado / Icarus)                    │
        │                                                         ▼
        └──────────────► Python golden model ──────► compare ──► verification_report.md
                          (predicts the answer)                  PASS / FAIL
```

You do **not** run the golden model on its own. You run `run_verification.py` (or one of the
compare scripts) from a terminal and it does the comparing for you.

## 1. Requirements

| Need | Notes |
|---|---|
| Python 3.8+ | No extra packages. Check with `python --version`. |
| One simulator | **Vivado XSIM** (already installed with Vivado) *or* Icarus Verilog (`iverilog`, `vvp`). Not needed for `--no-sim`. |
| An **ASCII-only** project path | Vivado XSIM and Icarus cannot open files under folders with accents or special characters (for example `Hình ảnh`, `Tài liệu`). Python itself does not care. If your clone lives in such a folder, run from a plain copy such as `C:\tdm_verify` (see section 6). |

## 2. Input file format

`input/input_vectors.hex` has one test vector per line: 8 hex digits = four bytes,
`CH0 CH1 CH2 CH3` (CH0 first). `//` starts a comment. Maximum 256 vectors.

```
a53cf05a      // CH0=A5  CH1=3C  CH2=F0  CH3=5A
11223344
```

Generate random vectors (writes `input/random_vectors.hex`):

```
python golden_model/random_regression.py --n 200 --seed 42
```

## 3. Way A — one command (recommended)

From the repository root (or from any folder, the paths are resolved for you):

```
python golden_model/run_verification.py                    # auto: iverilog if installed, else Vivado xsim
python golden_model/run_verification.py --sim xsim         # force Vivado XSIM
python golden_model/run_verification.py --sim iverilog     # force Icarus Verilog
python golden_model/run_verification.py --vectors input/random_vectors.hex
```

What it does: compile `src/*.v` + `techbench/tb_tdm_top_filebased.v`, run the simulation, then
compare the result files with the golden model and write the report.
The Vivado GUI is **not** needed; only the command-line tools `xvlog`, `xelab`, `xsim`.
They are found on `PATH` or in `C:\Xilinx\Vivado\<version>\bin` / `C:\AMD\Vivado\<version>\bin`.
If Vivado is installed elsewhere:

```
set VIVADO_BIN=C:\Xilinx\Vivado\2020.2\bin
```

XSIM runs in a scratch folder `sim_xsim/` (git-ignored); the repository sources are never modified.

Exit code: `0` all checks passed, `1` at least one check failed, `2` the simulation could not run.

## 4. Way B — you already simulate in the Vivado GUI

You have an input file and Vivado produces the output files; now compare them.
Vivado/XSIM cannot open files whose path has accents or special characters, so the files that
Vivado reads and writes must live in an **ASCII-only working folder** (below: `C:/tdm_work`),
even when the repository itself does not.

1. Create `C:\tdm_work` and copy the input file into it:
   `copy input\input_vectors.hex C:\tdm_work\`
2. In Vivado add `src/*.v` as design sources and `techbench/tb_tdm_top_filebased.v` as the
   simulation source and set it as top. (The project folder must also be ASCII-only.)
3. At the top of the testbench file that Vivado uses, set the four path parameters to
   **absolute paths with forward slashes** that point into the working folder. A relative path
   such as `input/input_vectors.hex` is resolved inside Vivado's `*.sim/sim_1/behav/xsim`
   folder, where the input does not exist (`ERROR: no vectors read ...`):

   ```verilog
   parameter INPUT_FILE   = "C:/tdm_work/input_vectors.hex";
   parameter OUTPUT_FILE  = "C:/tdm_work/rtl_output_vectors.hex";
   parameter STREAM_FILE  = "C:/tdm_work/rtl_stream_vectors.txt";
   parameter LATENCY_FILE = "C:/tdm_work/rtl_latency_vectors.txt";
   ```
4. Run Behavioral Simulation, then press **Run All** (Tcl console: `run all`) so the simulation
   reaches `$finish`. The console prints `TONG KET: N vector, 0 loi` and the three result files
   appear in `C:\tdm_work`.
5. Compare. Python has no problem with accents, so run this in the repository folder:

   ```
   python golden_model\run_verification.py --no-sim --vectors C:\tdm_work\input_vectors.hex --results C:\tdm_work
   ```

   `--no-sim` = "do not simulate, only compare the files that already exist";
   `--vectors` = the input file used; `--results` = the folder holding the files Vivado wrote
   (the report and the Excel workbook are written there too). Keep the file names exactly as above:
   the scripts look for `rtl_output_vectors.hex`, `rtl_stream_vectors.txt` and
   `rtl_latency_vectors.txt` next to an input called `input_vectors.hex`.

   Short form for the same thing (folder = the argument, else `$TDM_WORK`, else `~/TDM/verify`):

   ```
   python golden_model\run_verification.py --work C:\tdm_work
   ```

## 5. Way C — you only have an output file

If you only have the settled-output file (one line per vector, `CH0_OUT CH1_OUT CH2_OUT CH3_OUT`
as 8 hex digits), do the quick outputs-only check:

```
python golden_model/compare_vector_files.py --input input/input_vectors.hex --output path/to/rtl_output.hex
```

It does not check the bit stream or the latency; use way A or B for the full check.

## 6. If your clone path contains accents or spaces

Keep the repository where it is and test in a throw-away ASCII copy:

```
robocopy <repo>\src          C:\tdm_verify\src          /MIR
robocopy <repo>\techbench    C:\tdm_verify\techbench    /MIR
robocopy <repo>\input        C:\tdm_verify\input        /MIR
robocopy <repo>\golden_model C:\tdm_verify\golden_model /MIR /XD __pycache__ verification_logs
cd /d C:\tdm_verify
python golden_model\run_verification.py --sim xsim
```

Results are written to `C:\tdm_verify\golden_model\verification_logs\`. Copy that folder's files
into the repository if you want to commit them.

## 7. Excel results workbook

Every run also writes `verification_results.xlsx` next to the report (`--no-excel` to skip;
needs `pip install openpyxl`, otherwise a hint is printed and the run continues):

| Sheet | Content |
|---|---|
| `Summary` | run date/time, input file, simulator (`--sim-label "Vivado 2020.2 XSIM"`), totals, pass rate, overall status, latency min / max / average in cycles and ns, latency chart |
| `Results` | one row per vector: input, CH0..CH3, golden and RTL outputs, golden and RTL 32-bit streams, latency (cycles, ns), PASS/FAIL. All checks are Excel formulas; filters and colouring included |
| `History` | one row appended per run, to compare runs over time |

The clock period (10 ns, from `always #5 clk = ~clk` in the testbench) and the latency limit (41)
are editable yellow cells on `Summary`. In Excel's Protected View click *Enable Editing* so the
formulas calculate. The file is named after the input (`verification_results_<tag>.xlsx`).

## 8. What is compared, for every input vector

| Check | RTL side (written by `techbench/tb_tdm_top_filebased.v`) | Golden side |
|---|---|---|
| Bit stream | the 32 bits on `TDM_DATA` during one frame starting at `bit_count == 0` (`rtl_stream_*.txt`) | `TDMGoldenModel.serialize()` — MSB first, CH0 → CH3, compared cycle by cycle |
| Outputs | settled `CH0_OUT..CH3_OUT` (`rtl_output_*.hex`) | channels recovered by `TDMGoldenModel.deserialize()` |
| Latency | clocks from applying the vector until all four outputs are correct (`rtl_latency_*.txt`) | bound `MAX_LATENCY = 41` (see `latency_checker.py`) |

Measured latency: cold start 33 clocks, mid-stream change 40 clocks (allowed worst case 41).
Vector 0 is a cold start (counted from reset release); later vectors change the inputs at
`bit_count == 24`. A vector that repeats a byte of the previous one can show a shorter latency.

## 9. Reading the result

The terminal ends with a block such as

```
 vectors passed : 20/20
 latency check  : PASS
>>> ALL CHECKS PASSED
```

and `verification_logs/verification_report.md` has one row per vector (input, outputs match,
bit stream match, latency, PASS/FAIL). A failing vector is printed as `[FAIL] #<n> ... stream=BAD` followed by
`first wrong cycle <k>: golden=0 rtl=1`, which is where to start debugging the RTL.

## 10. Files

| File | Role |
|---|---|
| `golden_model.py` | Reference model (`serialize`, `deserialize`, `run_frame`) |
| `run_verification.py` | Compile + simulate + compare in one command |
| `compare_output.py` | Full RTL vs golden comparison + report |
| `export_excel.py` | Writes `verification_results.xlsx` (Summary / Results / History) |
| `compare_vector_files.py` | Quick outputs-only comparison |
| `latency_checker.py` / `timing_checker.py` | Latency bound / 32-bit frame length |
| `report_generator.py` | Writes the Markdown report from the real results |
| `random_regression.py` | Generates random input vectors |
| `tdm_cycle_model.py` | Prints the ideal serial stream cycle by cycle (for reading, not checking) |

## 11. Troubleshooting

| Message | Fix |
|---|---|
| `can't open file '...run_verification.py'` | The terminal is in the wrong folder. Open it in the repository root, or give the full path to the script. |
| `iverilog/vvp not found` | Use `--sim xsim`, or install Icarus Verilog. |
| `Vivado xvlog/xelab/xsim not found` | Set `VIVADO_BIN` to the Vivado `bin` folder (section 3). |
| `cannot open an output file` | The path contains non-ASCII characters or does not exist; use the ASCII copy (section 6 or 4). |
| `ERROR: no vectors read from ...` in Vivado | The testbench could not open the input file: the path is relative or contains non-ASCII characters. Use absolute `C:/...` paths in an ASCII folder (section 4). |
| `Cannot find ...rtl_stream_...txt` | The simulation has not produced the result files yet (run it to `$finish`), or the testbench is an old version without stream/latency output. |
| Simulation prints no `TONG KET` line | It stopped before `$finish`; use **Run All** in the Vivado GUI. |
| `endmodules` compile error | Typo on the last line of the testbench; it must be `endmodule`. |
