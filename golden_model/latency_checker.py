"""Latency check based on values MEASURED by the RTL testbench.

tb_tdm_top_filebased.v writes, per test vector, the number of clock cycles
from "vector applied to the channel inputs" until every output equals it
(file: verification_logs/rtl_latency_<tag>.txt, -1 = never matched).

Vector 0 is a cold start (counted from reset release); every later vector is
a mid-stream change, applied at bit_count == SYNC_BIT_COUNT = (N-1)*W (24 for 4 x 8).

The allowed maximum is the worst case of the architecture, for N channels of W bits:
    up to N*W - 1 cycles waiting for that channel's load slot (tx_shift_reg loads
    each channel once per N*W-cycle frame)
  + W cycles to serialise the word
  + 2 cycles (rx word_done register + tdm_demux output register)
  = N*W + W + 1 cycles            (41 for 4 x 8; 32 bit_count phases swept: min 34, max 41)
"""

MAX_LATENCY = 41                  # 4 x 8


def max_latency(num_channels=4, data_width=8):
    """Worst-case latency in clock cycles for NUM_CHANNELS x DATA_WIDTH."""
    return num_channels * data_width + data_width + 1


def check_latency(latencies, max_latency=MAX_LATENCY):
    """latencies: list of ints, index 0 = cold start. Returns a summary dict."""

    bad = [
        (i, lat) for i, lat in enumerate(latencies)
        if lat < 0 or lat > max_latency
    ]

    steady = [lat for lat in latencies[1:] if lat >= 0]

    return {
        "ok": len(bad) == 0 and len(latencies) > 0,
        "bad": bad,                                   # [(vector_index, latency)]
        "cold_start": latencies[0] if latencies else None,
        "steady_min": min(steady) if steady else None,
        "steady_max": max(steady) if steady else None,
        "max_allowed": max_latency,
    }


def report_latency(summary):
    print("\n=== LATENCY CHECK (measured by the RTL testbench) ===")
    print(f"Cold start (vector 0)  : {summary['cold_start']} clocks")
    print(f"Mid-stream min / max   : {summary['steady_min']} / {summary['steady_max']} clocks")
    print(f"Allowed maximum        : {summary['max_allowed']} clocks")
    for idx, lat in summary["bad"]:
        print(f"  vector #{idx}: latency {lat} is outside 0..{summary['max_allowed']}")
    print("PASS" if summary["ok"] else "FAIL")
