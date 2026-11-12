# How to simulate this project

This guide is for anyone who has just cloned the repository. Three things can be run, in increasing depth:

| What | Command | Simulator needed |
|---|---|---|
| System testbench (38 checks) | `python scripts/run_tests.py` | Icarus Verilog **or** Vivado |
| RTL vs Python golden model (every vector, bit by bit) | `python golden_model/run_verification.py` | Icarus Verilog **or** Vivado |
| Vivado GUI simulation with waveforms | see [Section 4](#4-vivado-gui-waveforms) | Vivado |

## 1. Prerequisites

| Need | Notes |
|---|---|
| Python 3.8+ | No packages needed. `python --version` to check. The Excel report in the golden model flow needs `python -m pip install openpyxl` (optional). |
| A simulator | **Icarus Verilog** (`iverilog`, `vvp`; Windows installer from <https://bleyer.org/icarus/>, Linux `sudo apt install iverilog`, macOS `brew install icarus-verilog`) **or** Xilinx **Vivado** (tested with 2020.2). |
| An **ASCII-only path** | Vivado XSIM and Icarus cannot open files located in folders with accents or special characters (for example `Hình ảnh`). Clone into something like `C:\work\tdm` if your home folder has such characters. |
| (optional) GTKWave | To open the `.vcd` waveforms written by the Icarus runs. |

Clone and enter the repository:

```bash
git clone https://github.com/Ygbzyem/TDM-4---Channel-Multiplerxer-Demultiplexer.git
cd TDM-4---Channel-Multiplerxer-Demultiplexer
```

## 2. Run all testbenches with one command

```bash
python scripts/run_tests.py                 # Icarus if installed, otherwise Vivado XSIM
python scripts/run_tests.py --sim xsim      # force Vivado XSIM
python scripts/run_tests.py --sim iverilog  # force Icarus Verilog
python scripts/run_tests.py tb_tdm_top -v   # only testbenches whose name contains "tb_tdm_top", show every check
```

Expected result:

```
testbench                     checks  passed  failed   result
----------------------------------------------------------------
tb_tdm_top                        38      38       0   PASS
----------------------------------------------------------------
TOTAL                             38      38       0   ALL PASSED
```

Exit code `0` means everything passed. Build products and waveforms (`sim/*.vcd`) are written to `sim/`, which is git-ignored.
If Vivado is not on your `PATH`, set `VIVADO_BIN` to its `bin` folder, for example
`set VIVADO_BIN=C:\Xilinx\Vivado\2020.2\bin` (Windows) or `export VIVADO_BIN=/tools/Xilinx/Vivado/2020.2/bin`.

### Run one testbench by hand (Icarus)

```bash
iverilog -g2012 -o sim_tb techbench/tb_tdm_top.v src/*.v
vvp sim_tb
gtkwave tb_tdm_top.vcd        # optional: view waveforms
```

On Windows PowerShell replace `src/*.v` with `(Get-ChildItem src\*.v).FullName`.

## 3. Compare the RTL with the Python golden model

```bash
python golden_model/run_verification.py                       # the 20 vectors in input/input_vectors.hex
python golden_model/random_regression.py --n 200 --seed 42    # create input/random_vectors.hex (200 random vectors)
python golden_model/run_verification.py --vectors input/random_vectors.hex

# another size: N x W bits per vector, same options for both scripts
python golden_model/random_regression.py --n 50 --channels 8 --width 16
python golden_model/run_verification.py --channels 8 --width 16 --vectors input/random_vectors_8x16.hex

# message mode: the cases of input/test_cases.txt + random cases, RTL result file vs golden result file
python golden_model/run_message_regression.py --sizes 4x8,4x16,8x8,3x12 --random 10
```

Add `--sim xsim` to use Vivado. The script compiles `src/*.v` with `techbench/tb_tdm_top_filebased.v`, simulates, then
compares every vector's bit stream (one frame, N·W bits), settled outputs and latency (limit N·W + W + 1) with the
golden model. Success looks like:

```
 vectors passed : 20/20
 latency check  : PASS
>>> ALL CHECKS PASSED
```

Results are written to `golden_model/verification_logs/`: three RTL result files, `verification_report.md`, and an Excel
workbook `verification_results.xlsx` that **grows with every run** (Summary / Results / History). Full details, the
meaning of each check, and troubleshooting are in [`golden_model/README.md`](../golden_model/README.md).

## 4. Vivado GUI (waveforms)

For the self-checking testbench `tb_tdm_top.v`:

1. **Create Project** → RTL Project, in an ASCII-only folder, any part (the project uses `xc7k70tfbv676-1`).
2. **Add Sources** → Add or create *design sources*: all files in `src/` (untick *Copy sources into project*).
3. **Add Sources** → *simulation sources*: `techbench/tb_tdm_top.v`.
4. In *Sources → Simulation Sources*, right-click the testbench → **Set as Top**.
5. **Run Simulation → Run Behavioral Simulation**, then **Run All** (Tcl console: `run all`) so it reaches `$finish`.
6. Read the Tcl console: every check prints `[PASS]` or `[FAIL]` and the last lines give the total.
   Add signals such as `DUT.bit_count`, `TDM_DATA`, `CH0_OUT` to the waveform window.

For the file-driven testbench `techbench/tb_tdm_top_filebased.v` (golden model flow with the GUI):

1. Put the input file and the result files in an **ASCII-only working folder**, e.g. `C:/tdm_work`
   (`copy input\input_vectors.hex C:\tdm_work\`).
2. In the testbench set `RUN_CASE = 0` (vector regression) and the four path parameters to absolute paths with **forward slashes**. Relative paths are resolved
   inside Vivado's `*.sim/sim_1/behav/xsim` folder, where the input does not exist (`ERROR: no vectors read`).

   ```verilog
   parameter INPUT_FILE   = "C:/tdm_work/input_vectors.hex";
   parameter OUTPUT_FILE  = "C:/tdm_work/rtl_output_vectors.hex";
   parameter STREAM_FILE  = "C:/tdm_work/rtl_stream_vectors.txt";
   parameter LATENCY_FILE = "C:/tdm_work/rtl_latency_vectors.txt";
   ```
3. Set it as top, Run Behavioral Simulation, **Run All**. The console ends with `TONG KET: N vector, 0 loi` and the three files appear.
   To run another input, copy it to `C:/tdm_work/input_vectors.hex`, then type `restart` and `run all` in the Tcl console.
4. Compare with the golden model from the repository folder (works with any path):

   ```bash
   python golden_model/run_verification.py --no-sim --vectors C:/tdm_work/input_vectors.hex --results C:/tdm_work
   ```

### One case from a text file, with waveform

```
// input/input_vectors.txt
NUM_CHANNELS = 4
DATA_WIDTH   = 8              // bits per slot
CH0 = 0123456789abcdef        // 8 slots: 01 23 45 67 89 ab cd ef
CH1 = deadbeef                // 4 slots, then 00
CH2 = cafe
CH3 = 5a
```

1. Put the case in `input/input_vectors.txt` (copy one from `input/test_cases.txt`).
2. In `techbench/tb_tdm_top_filebased.v` set `NUM_CHANNELS`, `DATA_WIDTH` to the values of the file. `REPO_DIR` can
   stay `"."` when the Vivado project is inside the repository (the testbench finds `input/` up to 6 folders above the
   simulation folder); otherwise set it to the repository folder (absolute path, forward slashes). The testbench stops
   with an error if the file is not found or its size does not match.
3. Run the simulation to the end (Vivado: Run Simulation, then **Run All**; Icarus:
   `iverilog -g2001 -o sim/tb techbench/tb_tdm_top_filebased.v src/*.v && vvp sim/tb` from the repository folder).
   → `results/rtl_result.txt`
4. `python golden_model/golden_model.py` → prints every step and writes `results/golden_result.txt`.
5. Open the two files side by side (VS Code: `code --diff results/rtl_result.txt results/golden_result.txt`).
   Only the `# source` line differs when RTL and model agree. Both files are overwritten by the next run.

In Vivado add `DUT/u_counter/channel_select`, `DUT/u_counter/bit_index`, `TDM_DATA`, `DUT/load`, `DUT/word_done`,
`DUT/demux_select` and `ch_out` (radix hexadecimal) to the waveform, then `restart` and `run all`. If the waveform
shows only X, it is zoomed on the first picoseconds: use **Zoom Fit**.

Per channel, the testbench has one scope `CH[0]`, `CH[1]`, ... (Scope window → `tb_tdm_top_filebased` → `CH[0]` →
select all objects → Add to Wave Window): `sent` (slot the device presents), `received` (its output), `expected`
(original slot from the input file that the output must hold now), `ok` (1 while `received == expected`),
`message_in` / `message_out` (whole message and the slots received so far) and `message_ok`. `all_ok` and
`all_messages_ok` cover every channel; `all_messages_ok` goes to 1 when the last slot arrives (2345 ns for the
example). A received slot appears N x W + 1 cycles after its frame starts, so `received` lags `sent` by one frame.

The vector regression of section 3 uses the same testbench with `RUN_CASE = 0`; `run_verification.py` sets it.

## 5. Synthesis (optional, Vivado)

```bash
vivado -mode batch -source scripts/synth.tcl
```

Writes `results/utilization_synth.rpt` and `results/timing_synth.rpt` (target `xc7k70tfbv676-1`, the clock constraint in
`constraint/constraints.xdc`). The numbers in the README come from the Vivado 2020.2 GUI flow after implementation (place and route); the script
only runs the synthesis step in batch mode and has not been run-tested here. Use an ASCII-only project path.

## 6. Troubleshooting

| Message | Fix |
|---|---|
| `ERROR: no simulator found` | Install Icarus Verilog or Vivado; for Vivado set `VIVADO_BIN` to its `bin` folder. |
| `iverilog` is not recognized | The installer folder is not on `PATH`: restart the terminal, or add `C:\iverilog\bin` to `PATH`. |
| `ERROR: no vectors read from ...` / `cannot open an output file` | Non-ASCII or relative path. Use an ASCII-only folder and absolute `C:/...` paths (Section 4). |
| `can't open file '...run_verification.py'` | The terminal is not in the repository folder, or the path starts with a stray `\`. |
| `Cannot find ...rtl_stream_...txt` | The simulation did not reach `$finish`; use **Run All**. |
| Vivado simulation finishes but the console shows no `TONG KET` line | Same as above: press **Run All** (do not just *Run for 1000 ns*). |
| `Excel skipped : openpyxl is not installed` | `python -m pip install openpyxl` (the verdict is unaffected). |
