# `tdm_top` — integration and timing glue layer

`tdm_top.v` wires the five sub-modules together and adds **four lines of glue logic**. The sub-modules are used
unchanged, and everything that makes the system behave correctly lives here.

```verilog
wire [4:0] bit_count_next = bit_count + 5'd1;
wire [1:0] mux_select    = bit_count_next[4:3];       // look one step ahead
wire       load          = (bit_count[2:0] == 3'b111);
wire       byte_boundary = (bit_count[2:0] == 3'b111); // same formula as load
reg  [1:0] demux_select;                              // channel_select delayed by one clock
always @(posedge clk) demux_select <= rst ? 2'b00 : channel_select;
```

## Why each line is needed

`tx_shift_reg` and `rx_shift_reg` are synchronous: a value loaded on a clock edge is visible only after that edge.

1. **`mux_select` looks one step ahead.** `tx_shift_reg` can only load on a clock edge, so to send channel X during the
   8 clocks of slot X, the multiplexer must already point at X on the clock edge that ends the previous slot.
2. **`load` / `byte_boundary` fire at the end of a slot** (`bit_count[2:0] == 7`), not at the start (`== 0`). Firing at the
   start delays every byte by one clock relative to its frame and lands each byte in the wrong output register.
3. **`demux_select` is a delayed copy of `channel_select`.** When `byte_done` rises, the live `channel_select` has already
   moved to the next channel, because `bit_count` never waits. `byte_done` is a registered pulse one clock later than `byte_boundary`,
   so the demultiplexer must use the selector value from one clock earlier.

Removing the look-ahead was simulated: the channels rotate permanently by one position, inputs `AA/BB/CC/DD` appear on
`CH0_OUT..CH3_OUT` as `DD/AA/BB/CC`. No bit is lost, so the stream looks fine on the wire while every byte lands in the wrong channel.

## Reset behaviour

`tx_shift_reg` preloads `mux_out` on reset instead of clearing to `8'h00`. `bit_count` is held at 0 while `rst` is high, so
`mux_select` already points at CH0 and `tx_shift` holds CH0's byte the moment `rst` is released. Without the preload the first byte
actually loaded would be CH1's and CH0 would only appear after a full extra frame.

## Real trace (inputs `CH0..CH3 = A5, 3C, F0, 5A`, cycle 0 = first cycle after reset is released)

Output of the simulation of `tdm_top` (Icarus Verilog), selected columns:

| cycle | `bit_count` | `mux_select` | `load` | `TDM_DATA` | `rx_data` | `byte_done` | `demux_select` | `CH0_OUT` `CH1_OUT` `CH2_OUT` `CH3_OUT` |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 1 | 00 | 0 | 0 | 00 00 00 00 |
| 7 | 7 | 1 | **1** | 1 | 00 | 0 | 0 | 00 00 00 00 |
| 8 | 8 | 1 | 0 | 0 | a5 | **1** | 0 | 00 00 00 00 |
| 9 | 9 | 1 | 0 | 0 | a5 | 0 | 1 | **a5** 00 00 00 |
| 15 | 15 | 2 | **1** | 0 | a5 | 0 | 1 | a5 00 00 00 |
| 16 | 16 | 2 | 0 | 1 | 3c | **1** | 1 | a5 00 00 00 |
| 17 | 17 | 2 | 0 | 1 | 3c | 0 | 2 | a5 **3c** 00 00 |
| 25 | 25 | 3 | 0 | 1 | f0 | 0 | 3 | a5 3c **f0** 00 |
| 33 | 1 | 0 | 0 | 0 | 5a | 0 | 0 | a5 3c f0 **5a** |

CH0 is the first channel to appear (cycle 9), the four outputs are all valid at cycle 33, which is the cold-start latency reported
by the golden model. At cycle 7 `load` fires while `mux_select` already points at CH1 (look-ahead); at cycle 8 `byte_done`
pulses while `demux_select` still holds CH0's selector, so the byte lands in `CH0_OUT` at cycle 9.
