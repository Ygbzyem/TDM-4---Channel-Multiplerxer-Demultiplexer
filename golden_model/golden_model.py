"""Reference (golden) model of the TDM multiplexer/demultiplexer.

The model is the algorithm of the design written in plain Python, from the
specification and independently of the RTL. The RTL implements the same steps
with registers; every step below names the RTL line that does the same job
(see docs/golden_vs_rtl.md for the full side-by-side table).

    TDMGoldenModel(num_channels=4, data_width=8)     # default = original 4 x 8 design

Algorithm
    serialize   : channel 0 first, inside a channel the MSB first, one bit per clock.
    deserialize : shift the bits back in, MSB first; every data_width bits one
                  word is complete and goes to the output of its channel.
    message_slots / frames : a whole message per device (hex) is cut into
                  data_width-bit slots; frame f carries slot f of every channel,
                  CH0 first, and a finished channel sends 0 (done by the testbench,
                  which plays the devices).
    timeline    : cycle-accurate expectation for one case (cycle 0 = first clock
                  cycle after reset is released).

Timing of the ideal model (the RTL needs the same number of register stages):
    * bit b of channel c is on TDM_DATA in cycle  c*W + (W-1-b)
    * after the last bit of a word the receiver needs RX_PIPELINE = 2 registered
      steps (rx_data/word_done, then the output register), so CHc_OUT holds the
      new value from cycle (c+1)*W - 1 + 2 = (c+1)*W + 1; slot f of channel c
      arrives one frame (N*W cycles) later per slot: f*N*W + (c+1)*W + 1
    * cold-start latency = N*W + 1 cycles (33 for 4 x 8)
"""


class TDMGoldenModel:

    RX_PIPELINE = 2          # RTL: rx_shift_reg (rx_data, word_done) + tdm_demux (ch_out register)

    def __init__(self, num_channels=4, data_width=8):
        if num_channels < 2 or data_width < 2:
            raise ValueError("num_channels and data_width must both be >= 2")
        self.num_channels = num_channels                 # RTL: parameter NUM_CHANNELS
        self.data_width = data_width                     # RTL: parameter DATA_WIDTH
        self.frame_cycles = num_channels * data_width    # RTL: tdm_counter wraps after N*W cycles
        self.mask = (1 << data_width) - 1                # RTL: every word register is DATA_WIDTH bits

    # ------------------------------------------------------------------ transmit side
    def serialize(self, channels):
        stream = []
        for ch in range(self.num_channels):              # RTL tdm_counter: channel_select 0 .. N-1
            word = channels[ch]                          # RTL tdm_mux: mux_out = word of channel_select
            for i in range(self.data_width - 1, -1, -1): # RTL tdm_counter: bit_index 0 .. W-1 (MSB first)
                stream.append((word >> i) & 1)           # RTL tx_shift_reg: serial_out = tx_shift[W-1], shift left
        return stream

    # ------------------------------------------------------------------ receive side
    def deserialize(self, stream):
        outputs = []
        word = 0
        for t, bit in enumerate(stream):
            word = ((word << 1) | bit) & self.mask       # RTL rx_shift_reg: rx_shift <= {rx_shift[W-2:0], serial_data}
            if t % self.data_width == self.data_width - 1:   # RTL tdm_top: word_boundary = (bit_index == W-1)
                outputs.append(word)                     # RTL rx_shift_reg: rx_data <= word; tdm_demux writes ch_out
        return outputs

    def run_frame(self, *channels):
        if len(channels) != self.num_channels:
            raise ValueError(f"expected {self.num_channels} channel values, got {len(channels)}")
        tx = [c & self.mask for c in channels]
        stream = self.serialize(tx)                      # RTL: CH inputs -> TDM_DATA
        recovered = self.deserialize(stream)             # RTL: TDM_DATA -> CH outputs
        result = {"stream": stream, "outputs": recovered}
        for i, v in enumerate(recovered):
            result[f"ch{i}_out"] = v                     # keeps the old keys ch0_out .. ch3_out
        return result

    # ------------------------------------------------------------------ timing
    def valid_cycle(self, channel, frame=0):
        """First cycle in which CH<channel>_OUT holds the word of slot <frame>."""
        last_bit_cycle = frame * self.frame_cycles + (channel + 1) * self.data_width - 1   # RTL: word_boundary = 1
        return last_bit_cycle + self.RX_PIPELINE                # RTL: + word_done register + ch_out register

    def cold_start_latency(self):
        return self.valid_cycle(self.num_channels - 1)

    # ------------------------------------------------------------------ messages (devices)
    def message_slots(self, hex_message):
        """Cut one message (hex digits, MSB first) into data_width-bit slots;
        the last slot is padded with 0. Testbench: read_message_case."""
        bits = [(int(d, 16) >> (3 - j)) & 1 for d in hex_message for j in range(4)]
        w = self.data_width
        n = -(-len(bits) // w)
        bits += [0] * (n * w - len(bits))
        return [int("".join(map(str, bits[k * w:(k + 1) * w])), 2) for k in range(n)]

    def frames(self, slot_lists):
        """Frame f = slot f of every channel; a finished channel sends 0. Testbench: apply_frame."""
        n_frames = max(len(sl) for sl in slot_lists)
        return [[sl[f] if f < len(sl) else 0 for sl in slot_lists] for f in range(n_frames)]

    def rebuild_message(self, words, hex_digits):
        """Put received slots back together and keep the first hex_digits digits."""
        bits = []
        for word in words:
            bits += [(word >> i) & 1 for i in range(self.data_width - 1, -1, -1)]
        return "".join(format(int("".join(map(str, bits[4 * k:4 * k + 4])), 2), "x") for k in range(hex_digits))

    def timeline(self, channels, cycles=None):
        """Expected signals in each cycle when one word per channel is sent (one frame)."""
        return self.timeline_frames([list(channels)], cycles)

    def timeline_frames(self, frames, cycles=None):
        """Expected value of every observable signal in each cycle of one case.

        frames[f][c] is the word of channel c in frame f; after the last frame every
        channel sends 0. Returns a list of dicts: cycle, frame, ch, bit, tdm_data, outputs.
        """
        n, w, fc = self.num_channels, self.data_width, self.frame_cycles
        if cycles is None:
            cycles = len(frames) * fc + 2                       # until the last word is out
        word_of = lambda f, c: frames[f][c] if f < len(frames) else 0
        rows = []
        for t in range(cycles):
            f = t // fc
            sent = self.serialize([word_of(f, c) for c in range(n)])
            outs = []
            for c in range(n):
                done = [g for g in range(f + 1) if self.valid_cycle(c, g) <= t]
                outs.append(word_of(done[-1], c) if done else 0)    # RTL tdm_demux: reset value 0
            rows.append({
                "cycle": t,
                "frame": f,
                "ch": (t // w) % n,                      # RTL: tdm_counter.channel_select
                "bit": w - 1 - (t % w),                  # RTL: DATA_WIDTH-1 - tdm_counter.bit_index
                "tdm_data": sent[t % fc],                # RTL: TDM_DATA
                "outputs": outs,
            })
        return rows

if __name__ == "__main__":
    gm = TDMGoldenModel()
    result = gm.run_frame(0x12, 0x34, 0x56, 0x78)
    print("TDM Stream:", "".join(map(str, result["stream"])))
    print("Recovered :", [hex(v) for v in result["outputs"]])
    print("PASS" if result["outputs"] == [0x12, 0x34, 0x56, 0x78] else "FAIL")

    gm16 = TDMGoldenModel(num_channels=4, data_width=16)
    r16 = gm16.run_frame(0x1234, 0xABCD, 0x00FF, 0x8001)
    print("4 x 16    :", [hex(v) for v in r16["outputs"]],
          "latency", gm16.cold_start_latency(), "cycles")
