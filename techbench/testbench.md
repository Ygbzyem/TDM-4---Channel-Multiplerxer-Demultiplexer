# `tb_tdm_top.v` — Testbench Explained

## What this testbench is for

`tb_tdm_top.v` is the **system-level testbench** for the complete TDM mux/demux design (`tdm_top.v`, which wires together `tdm_counter`, `tdm_mux`, `tx_shift_reg`, `rx_shift_reg`, and `tdm_demux`). It does not test any module in isolation — it drives the 4 parallel input channels (`CH0..CH3`), lets the whole pipeline run, and checks that the 4 parallel output channels (`CH0_OUT..CH3_OUT`) eventually match what went in.

It is organized into three independent layers of checking, each catching a different class of bug:

| Part | What it checks | Why it exists |
|---|---|---|
| PART 1 — round-trip per frame | `CH_OUT` eventually equals `CH_IN` | Basic sanity: does data survive the trip end-to-end? |
| PART 2 — bit-level check on `TDM_DATA` | The exact 32-bit serial stream matches `{CH0,CH1,CH2,CH3}` bit-for-bit | Catches a subtle bug class: if the transmit side and the receive side each have a timing bug that happens to cancel out, PART 1 can pass by accident while the actual wire is wrong. PART 2 inspects the raw serial line directly, so it can't be fooled that way. |
| PART 3 — random regression | 20 back-to-back random frames all round-trip correctly | Simulates continuous, unpredictable traffic instead of a few hand-picked values — the kind of test that would catch an edge case PART 1's fixed values happen to miss. |

## Signals and DUT hookup

```verilog
reg clk = 0;
reg rst;
reg [7:0] CH0, CH1, CH2, CH3;
wire       TDM_DATA;
wire [7:0] CH0_OUT, CH1_OUT, CH2_OUT, CH3_OUT;

integer errors = 0;
integer checks = 0;

always #5 clk = ~clk;
```

`errors`/`checks` are simple running counters, printed at the very end as a pass/fail summary. `always #5 clk = ~clk;` is the clock generator — see the "How long is one clock cycle" section below for exactly what this means in nanoseconds.

The DUT (`tdm_top`) is instantiated once with the default parameters `NUM_CHANNELS = 4`, `DATA_WIDTH = 8`. Its ports are
buses: the four input bytes are packed as `.ch_in({CH0, CH1, CH2, CH3})` (channel 0 = most significant byte, like the
packed vectors in `input/*.hex`) and the outputs are unpacked the same way with `.ch_out({CH0_OUT, CH1_OUT, CH2_OUT, CH3_OUT})`, so the rest of the testbench still works with `CH0..CH3`.
`DUT.u_counter.bit_count` (used in PART 2) is the frame position `{channel_select, bit_index}`, 0 to 31.

## The three helper tasks

### `check_channel` — PART 1's building block

```verilog
task check_channel(input [7:0] expected, input [7:0] actual, input [255:0] label);
    begin
        checks = checks + 1;
        if (expected !== actual) begin
            $display("[FAIL] %0s : expected=%h actual=%h", label, expected, actual);
            errors = errors + 1;
        end else begin
            $display("[PASS] %0s : %h", label, actual);
        end
    end
endtask
```

Nothing more than "compare two bytes, print PASS/FAIL, bump the counters." Note it uses `!==` (case-inequality), not `!=` — this matters in Verilog because `!==` also catches `X`/`Z` mismatches that `!=` would silently ignore. If a signal is still unknown (`X`) when this runs, `!==` correctly reports a mismatch instead of masking the bug.

### `capture_and_check_serial_frame` — PART 2's building block

```verilog
task capture_and_check_serial_frame(input [7:0] e0, e1, e2, e3, input [255:0] label);
    begin
        while (DUT.u_counter.bit_count !== 5'd0) @(posedge clk);
        captured_frame = 32'h0;
        for (k = 0; k < 32; k = k + 1) begin
            captured_frame = {captured_frame[30:0], TDM_DATA};
            @(posedge clk);
        end
        checks = checks + 1;
        if (captured_frame !== {e0, e1, e2, e3}) ...
    end
endtask
```

Two things worth understanding here:

1. **`while (DUT.u_counter.bit_count !== 5'd0) @(posedge clk);`** — this is a *hierarchical reference*: the testbench reaches directly into the DUT's internals (`DUT` → `u_counter` → `bit_count`) to read a signal that isn't even a port of `tdm_top`. This is completely legal in simulation (it's not synthesizable, but this file is testbench-only, so that's fine) and it's the only way to reliably start sampling *exactly* at the beginning of a frame (`bit_count == 0`) instead of at some arbitrary point mid-frame.
2. **The sampling loop itself** shifts `TDM_DATA` into `captured_frame` one bit per clock, 32 times — that's exactly one full frame (4 bytes × 8 bits). The result is compared against the expected 32-bit value built from `{e0,e1,e2,e3}` (MSB-first, channel order CH0→CH1→CH2→CH3). This is a direct, bit-exact check of the wire — nothing about the demux side can hide a bug from this task, because it never looks at `CH_OUT` at all.

### `run_random_frame` — PART 3's building block

```verilog
task run_random_frame(input integer frame_no);
    begin
        CH0 = $random; CH1 = $random; CH2 = $random; CH3 = $random;
        repeat (48) @(posedge clk);
        ...
    end
endtask
```

Straightforward: pick 4 random bytes, wait, check round-trip. Called 20 times in a loop in PART 3.

## Walking through `initial begin ... end`

### PART 1 — round-trip per frame

```verilog
rst = 1;
CH0 = 8'hA5; CH1 = 8'h3C; CH2 = 8'hF0; CH3 = 8'h5A;
repeat (2) @(posedge clk);
#1;
rst = 0;

repeat (48) @(posedge clk);
check_channel(CH0, CH0_OUT, "WARM - CH0_OUT");
... (CH1, CH2, CH3)
```

This block: hold reset for 2 full clock cycles (with values already parked on `CH0..CH3` so they're stable the moment reset lifts), release reset, wait 48 cycles (comfortably more than the ~11 cycles it actually takes for the first byte to land — see the timing breakdown below), then check all 4 outputs.

**The `#1;` before `rst = 0;` is a deliberate fix, not an accident** — see the dedicated section below on why it's there.

The same pattern (`CH0=...; repeat(48)@(posedge clk); check_channel(...)`) repeats two more times with different values (`11/22/33/44`, then `00/FF/01/80` — the last one deliberately testing the all-zero and all-one boundary bytes), and then once more with a **mid-stream reset**:

```verilog
rst = 1;
repeat (2) @(posedge clk);
#1;
rst = 0;
CH0 = 8'h55; CH1 = 8'h66; CH2 = 8'h77; CH3 = 8'h88;
repeat (48) @(posedge clk);
check_channel(...)
```

This confirms the design recovers cleanly from a reset that happens *in the middle of normal operation*, not just from power-up.

### PART 2 — bit-level check

```verilog
CH0 = 8'hA5; CH1 = 8'h3C; CH2 = 8'hF0; CH3 = 8'h5A;
repeat (64) @(posedge clk);
capture_and_check_serial_frame(CH0, CH1, CH2, CH3, "bit-check frame 1 (A5/3C/F0/5A)");

CH0 = 8'h00; CH1 = 8'hFF; CH2 = 8'h81; CH3 = 8'h7E;
repeat (64) @(posedge clk);
capture_and_check_serial_frame(...);
```

`repeat(64)` here (2 full 32-cycle frames) simply gives the pipeline plenty of time to flush out the previous values before the bit-exact capture starts — it doesn't need to be frame-aligned the way it matters for a clean waveform demo (see the alignment note below), because `capture_and_check_serial_frame` itself waits for `bit_count == 0` before sampling anyway.

### PART 3 — random regression

```verilog
for (f = 1; f <= 20; f = f + 1)
    run_random_frame(f);
```

20 random frames, back to back, each one an independent round-trip check.

### Final summary

```verilog
$display(" TONG KET: %0d check, %0d loi", checks, errors);
if (errors == 0) $display(" >>> TAT CA TEST PASSED");
else              $display(" >>> CO %0d TEST FAILED", errors);
```

38 checks total (4+4+4+4 in PART 1, 2 in PART 2, 20 in PART 3) — plain arithmetic, not a magic number.

## Why the `#1;` before every `rst = 0;` matters

This is the single most important detail in this file, and it's easy to miss because it looks like a no-op.

Without it, the code would be:

```verilog
rst = 1;
repeat (2) @(posedge clk);
rst = 0;             // <-- changes rst in the SAME instant as the last @(posedge clk)
```

The problem: at that exact clock edge, **two things are scheduled to happen at the same simulation time** — the DUT's own `always @(posedge clk)` blocks (inside `tdm_counter` and `tx_shift_reg`) are trying to *read* `rst` to decide whether to reset, at the very same instant the testbench is trying to *write* `rst` to 0. The Verilog language standard does **not** guarantee which of those two happens first when they're triggered by the same clock edge — it's simulator-defined. Icarus Verilog happened to resolve it one way (DUT reads the old value, `rst=1`, correctly); Vivado's XSIM resolved it the other way in this exact scenario (DUT reads the new value, `rst=0`, one edge too early) — same RTL, same testbench, different result, purely because of this race.

The concrete symptom this caused: the fix in `tx_shift_reg.v` (preloading CH0's byte during reset) depends on `bit_count` having already settled to `0` for at least one full clock cycle before reset is released. If the reset is effectively cut one cycle short by this race, the preload captures garbage instead of CH0, and the very first byte to appear on `TDM_DATA` is wrong — which showed up as **CH1 appearing before CH0** after reset, on Vivado only.

Adding `#1;` forces the `rst = 0;` assignment to happen a moment *after* that clock edge has fully settled (after the DUT's own registers have already committed their values for that edge), which removes the ambiguity entirely — the DUT is now guaranteed to have seen `rst = 1` cleanly for the full 2 cycles, regardless of which simulator is running it.

**Rule of thumb this generalizes to:** never change a control signal (`rst`, `enable`, an input the DUT samples synchronously, etc.) in the exact same statement/instant as a `@(posedge clk)` your own testbench just waited on. Either add a small delay (`#1;`) before changing it, or change it on the opposite clock edge (`@(negedge clk)`), so there's never a same-instant race with the DUT's own clocked logic.

## Why `bit_count` matters when you change `CH0..CH3` mid-simulation

`tdm_counter`'s `bit_count` never "knows" that you just changed the 4 input channels — it just keeps counting `0→31→0→31→...` forever, with no way to reset itself except the real `rst` signal. `tdm_mux` is purely combinational and just reads whatever is currently on `CH0..CH3` according to whichever channel's turn it currently is.

This has a direct, testable consequence: **which channel is the first to reflect newly-changed data depends entirely on what `bit_count` happens to be at the exact moment you change the inputs** — not on which channel is "CH0." If you change the inputs while `bit_count` is, say, `9` (inside CH1's window), the rotation just continues from there: CH2 gets the new data next, then CH3, then CH0, then CH1 last.

This testbench's PART 1 changes `CH0..CH3` after `repeat(48) @(posedge clk);` between frames. Since one frame is 32 cycles, **48 is not a multiple of 32**, so each time PART 1 moves to a new set of values, it lands on a different, somewhat arbitrary point inside the 32-cycle rotation — which is why the "first channel to show new data" can look different from run to run, or between simulators (small extra startup latency, e.g. Vivado's `glbl` GSR pulse, shifts the exact cycle count slightly). This is *not* a bug in the design; `check_channel` still waits long enough (48 cycles, far more than the ~11 cycles actually needed) that by the time it checks, all four channels are correct regardless of the order they arrived in.

If a demo/waveform needs to look identical and predictable every single run (e.g., for a presentation), the fix is to make the wait a clean **multiple of 32** (e.g. `repeat(64)` instead of `repeat(48)`) — that guarantees `bit_count` returns to the exact same phase every time you change the inputs, so the rotation order becomes fixed and reproducible (verified: with `repeat(64)`, every single frame change lands on the same `bit_count` value and produces the identical CH1→CH2→CH3→CH0 order, run after run). It does not by itself make CH0 the first channel again — only an actual reset does that, because only reset forces `bit_count` back to exactly 0.

## How long is one clock cycle, concretely

```verilog
`timescale 1ns/1ps
...
always #5 clk = ~clk;
```

`timescale 1ns/1ps` means: 1 unit of delay (like the `5` in `#5`) = 1 nanosecond, and the simulator's internal time resolution is 1 picosecond. `#5` toggles `clk` every 5ns, so the half-period is 5ns and **one full clock cycle (rising edge to rising edge) is 10ns**.

Two ways to confirm this for any testbench, without re-deriving it from code every time:
- Read the `` `timescale `` line at the top of the file, and the number after `#` in the `always #N clk = ~clk;` line — the period is `2×N` in whatever unit `timescale` declares.
- Or, in the waveform viewer, just click on two consecutive rising edges of `clk` and read the time difference the tool reports — this works regardless of what the source code says.

## A concrete timing trace: why CH0_OUT first changes at 105ns

Starting from `rst` going high with `CH0=A5,CH1=3C,CH2=F0,CH3=5A` already parked, and clocks at 5, 15, 25, 35, ... ns:

| Time | `bit_count` | Event |
|---|---|---|
| 5ns, 15ns | held at 0 (reset) | `rst` held for 2 full cycles; `tx_shift_reg` preloads CH0's byte (`A5`) during this window |
| 15ns → 85ns | 0 → 7 | counter runs normally, `tx_shift_reg` shifts `A5` out one bit per cycle on `TDM_DATA` |
| 85ns | 7 | `load`/`byte_boundary` fire (`bit_count[2:0]==7`): TX loads CH1's byte for next; RX schedules `byte_done` |
| 95ns | 8 | `byte_done` becomes 1 (it's a **registered** signal inside `rx_shift_reg`, so it needs this extra edge) |
| 105ns | 9 | `tdm_demux` (a *separate* clocked module) sees `byte_done=1` on its own next edge and writes `CH0_OUT <= A5` |

The two separate one-cycle delays at 85→95ns and 95→105ns are the reason the total latency isn't a "clean" round number — each one comes from a genuinely registered (clocked) signal in the pipeline (`byte_done`, then the demux's own output register), not from anything accidental.

## The three all-`X` (red) signals you may see in the waveform

`captured_frame[31:0]`, `k[31:0]`, and `f[31:0]` are **testbench-only bookkeeping variables** — they don't exist in the actual hardware (`tdm_top`), only in this file:

- `captured_frame` — the 32-bit shift accumulator used by `capture_and_check_serial_frame` in PART 2.
- `k` — the loop counter for that same task's 32-bit sampling loop.
- `f` — the loop counter for PART 3's 20-frame random loop.

They show up as all-`X` (and most waveform viewers, including Vivado, color an all-unknown bus red as a visual warning) simply because they haven't been assigned a value yet — PART 2 and PART 3 haven't started executing yet at that point in the simulation. Once the simulation reaches those parts, these signals get real numeric values and the red/X display goes away. This is expected, not an error.