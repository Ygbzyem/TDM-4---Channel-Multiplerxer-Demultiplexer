# Golden model vs RTL — line by line

The RTL was written from the algorithm that `golden_model/golden_model.py` describes. The golden model is the
algorithm without a clock; the RTL performs the same steps with registers, one bit per clock. The table maps every
step of the model to the RTL line that performs it (line numbers of the current files).

## 1. Same step, two descriptions

| # | Golden model (`golden_model/golden_model.py`) | RTL | What both lines do |
|---|---|---|---|
| 1 | L38–39 `self.num_channels`, `self.data_width` | `tdm_counter.v` L17–18 and every module: `parameter NUM_CHANNELS`, `DATA_WIDTH` | Size of the system |
| 2 | L40 `frame_cycles = num_channels * data_width` | `tdm_counter.v` L53–58: both counters wrap after N × W clocks | Length of one frame |
| 3 | L41 `mask = (1 << data_width) - 1` | every word register is `[DATA_WIDTH-1:0]` | A word has exactly W bits |
| 4 | L46 `for ch in range(self.num_channels)` | `tdm_counter.v` L55–58: `channel_select` counts 0 … N−1, then wraps | Channels are sent in the order CH0, CH1, … |
| 5 | L47 `word = channels[ch]` | `tdm_mux.v` L39: `mux_out = ch_in[(N-1-i)*W +: W]` when `channel_select == i` | Pick the word of the current channel |
| 6 | L48 `for i in range(W-1, -1, -1)` | `tdm_counter.v` L53, L54, L61: `bit_index` counts 0 … W−1 inside a word | Walk through the bits of one word |
| 7 | L49 `stream.append((word >> i) & 1)` | `tx_shift_reg.v` L22 load, L24 `tx_shift <= {tx_shift[W-2:0], 1'b0}`, L27 `serial_out = tx_shift[W-1]` | Put the bits on the wire, MSB first, one per clock |
| 8 | L57 `word = ((word << 1) \| bit) & mask` | `rx_shift_reg.v` L30 `rx_shift <= {rx_shift[W-2:0], serial_data}` | Shift the received bit in, MSB first |
| 9 | L58 `if t % W == W - 1` | `tdm_top.v` L75 `last_bit = (bit_index == W-1)`, L82 `word_boundary = last_bit`; `rx_shift_reg.v` L32 | The last bit of a word has arrived |
| 10 | L59 `outputs.append(word)` | `rx_shift_reg.v` L34–35 `rx_data <= {rx_shift[W-2:0], serial_data}`, `word_done <= 1`; `tdm_demux.v` L41–44 writes `ch_out` of the selected channel | The complete word goes to the output of its channel |
| 11 | L33 `RX_PIPELINE = 2`, L76–77 `valid_cycle = f*N*W + (c+1)*W - 1 + 2` | 1st register: `rx_shift_reg.v` L34–35; 2nd register: `tdm_demux.v` L44 | An output changes 2 clocks after the last bit of its word; slot f arrives f frames later |
| 12 | L125 `... else 0` | `tdm_demux.v` L40 reset `ch_out <= 0` | Outputs are 0 until their word arrives |
| 13 | L129 `"ch": (t // w) % n`, L130 `"bit": w - 1 - (t % w)` | `tdm_counter.v` `channel_select`, `bit_index` | Which channel and which bit are on the wire in cycle t |
| 14 | L131 `"tdm_data": sent[t % fc]` | `tdm_top` output `TDM_DATA` | The bit on the wire in cycle t |

## 2. Messages cut into slots: golden model vs testbench

A case gives every device a whole message. The RTL itself sends one slot per channel per frame; the testbench plays the
devices that present the next slot every frame and collects what comes out. The golden model does the same on paper:

| Golden model (`golden_model.py`) | Testbench (`techbench/tb_tdm_top_filebased.v`) | What both do |
|---|---|---|
| L83–90 `message_slots()` | L374 `read_message_case`, L424 `word[W-1-b] = ... msg_bit(c, k) : 0` | Cut the hex message into W-bit slots, MSB first, last slot padded with 0 |
| L92–95 `frames()`: `sl[f] if f < len(sl) else 0` | L434–440 `apply_frame`: `(f < n_slots[c]) ? slot_mem[...] : 0`; L521 next slot in the last cycle of a frame | Frame f carries slot f of every channel; a finished channel sends 0 |
| L97–102 `rebuild_message()` | L500 collect the word from `ch_out`; L538 rebuild the message | Put the received slots of a channel back together |

## 2. Only in the RTL, and why

The golden model has no clock, so it can take "the word of the channel now" and "the word that just arrived" directly.
The RTL registers every step, so each register adds one clock of delay. The glue in `tdm_top.v` exists only to keep
the RTL on the schedule that the golden model describes:

| RTL line | Why it is needed | How the golden model checks it |
|---|---|---|
| `tdm_top.v` L77–79 `mux_select = last_bit ? next_channel : channel_select` | `tx_shift_reg` loads on the edge that ends a word, so the mux must already point at the next channel | trace column `ch`/`TDM_DATA`: a wrong select puts the wrong bits on the wire |
| `tdm_top.v` L81 `load = last_bit` | load at the end of a word, not at the start | `TDM_DATA` must follow row 7 cycle by cycle |
| `tdm_top.v` L87–89 `demux_select <= channel_select` | `word_done` comes one clock after `word_boundary`; the live channel has already moved on | outputs must appear in the right channel at `valid_cycle` (row 11) |
| `tx_shift_reg.v` L20 reset preloads `mux_out` | CH0 must be the first word on the wire after reset | the trace must start with CH0, bit W−1, in cycle 0 |

Without these lines the RTL still moves every bit, but the channels rotate (`AA BB CC DD` → `DD AA BB CC`). The
one-case comparison (README section 8.4) shows this immediately as
differing lines between `rtl_result.txt` and `golden_result.txt`.
