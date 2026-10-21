# Golden model verification

Python reference model + automatic comparison against the RTL simulation.

## Quick start (from any directory)

```
python golden_model/run_verification.py                                    # the 20 vectors in input/input_vectors.hex
python golden_model/random_regression.py --n 200 --seed 42                 # create input/random_vectors.hex
python golden_model/run_verification.py --vectors input/random_vectors.hex # run the random vectors
```

Needs Python 3 (no packages) and **one** simulator: Icarus Verilog (`iverilog`, `vvp`) or Vivado XSIM.
`--sim auto` (default) uses `iverilog` if installed, otherwise Vivado `xsim`.
Exit code `0` = all PASS, `1` = a check failed, `2` = simulation could not run.

## What is compared, for every input vector

| Check | RTL side (written by `techbench/tb_tdm_top_filebased.v`) | Golden side |
|---|---|---|
| Bit stream | the 32 bits on `TDM_DATA` during one frame starting at `bit_count == 0` (`rtl_stream_*.txt`) | `TDMGoldenModel.serialize()` — MSB first, CH0 -> CH3, compared cycle by cycle |
| Outputs | settled `CH0_OUT..CH3_OUT` (`rtl_output_*.hex`) | channels recovered by `TDMGoldenModel.deserialize()` |
| Latency | clocks from applying the vector until all four outputs are correct (`rtl_latency_*.txt`) | bound `MAX_LATENCY = 41` (see `latency_checker.py`) |

Result: `verification_logs/verification_report[_<tag>].md`.

## Files

| File | Role |
|---|---|
| `golden_model.py` | Reference model (`serialize`, `deserialize`, `run_frame`) |
| `compare_output.py` | Full RTL vs golden comparison + report |
| `compare_vector_files.py` | Quick outputs-only comparison |
| `latency_checker.py` / `timing_checker.py` | Latency bound / 32-bit frame length |
| `report_generator.py` | Writes the Markdown report from the real results |
| `random_regression.py` | Generates random input vectors (and a golden-model self-test) |
| `run_verification.py` | Compile + simulate + compare in one command |
| `tdm_cycle_model.py` | Prints the ideal serial stream cycle by cycle (for reading, not checking) |

## Running with Vivado XSIM (no Icarus needed)

```
python golden_model/run_verification.py --sim xsim
```

The script finds `xvlog` / `xelab` / `xsim` on `PATH`, or in `C:\Xilinx\Vivado\<ver>\bin` /
`C:\AMD\Vivado\<ver>\bin`. If Vivado lives elsewhere, point to its `bin` folder first:

```
set VIVADO_BIN=C:\Xilinx\Vivado\2023.2\bin
```

It compiles scratch copies of `src/*.v` + the testbench in `sim_xsim/` (git-ignored; repo files are
not modified), runs to `$finish`, then compares with the golden model. The path of the project must be
ASCII-only (no accents / special characters) because XSIM cannot open such paths.

Manual alternative (Vivado GUI): run `tb_tdm_top_filebased` with **Run All** so the three result files
appear in `golden_model/verification_logs/`, then `python golden_model/run_verification.py --no-sim`.

## Notes

* The testbench holds at most `MAX_VECTORS = 256` vectors.
* Vector 0 is a cold start (latency counted from reset release); later vectors are mid-stream
  changes applied at `bit_count == 24`. Vectors that repeat a byte of the previous vector can
  show a shorter latency, because that channel needs no update.
