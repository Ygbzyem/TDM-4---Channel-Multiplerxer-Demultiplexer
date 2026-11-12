"""Tiny cycle printer: which bit is on TDM_DATA in every clock cycle of one frame.

    python golden_model/tdm_cycle_model.py                 # 4 x 8, channels 12 34 56 78
    python golden_model/tdm_cycle_model.py --channels 3 --width 12 abc 123 fff
"""

import argparse


class TDMCycleModel:

    def __init__(self, num_channels=4, data_width=8):
        self.num_channels = num_channels
        self.data_width = data_width

    def run_frame(self, *channels):
        """Channel 0 first, MSB first: one (channel, bit, value) per clock cycle."""
        serial_stream = []
        for ch, word in enumerate(channels):
            for bit in range(self.data_width - 1, -1, -1):
                serial_stream.append((ch, bit, (word >> bit) & 1))
        return serial_stream


def print_cycles(stream):
    print("CLK | CH | BIT | DATA")
    for clk, (ch, bit, value) in enumerate(stream):
        print(f"{clk:3d} | {ch:2d} | {bit:3d} |  {value}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().split("\n")[0])
    ap.add_argument("--channels", type=int, default=4)
    ap.add_argument("--width", type=int, default=8)
    ap.add_argument("words", nargs="*", help="one hex word per channel (default 12 34 56 78)")
    a = ap.parse_args()
    words = [int(x, 16) for x in a.words] if a.words else [0x12, 0x34, 0x56, 0x78][:a.channels]
    if len(words) != a.channels:
        raise SystemExit(f"give {a.channels} words")
    print_cycles(TDMCycleModel(a.channels, a.width).run_frame(*words))
