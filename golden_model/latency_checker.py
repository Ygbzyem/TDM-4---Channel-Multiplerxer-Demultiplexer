"""Latency check based on values MEASURED by the RTL testbench.

tb_tdm_top_filebased.v writes, per test vector, the number of clock cycles
from "vector applied to CH0..CH3" until all four CHx_OUT equal it
(file: verification_logs/rtl_latency_vectors.txt, -1 = never matched).

Vector 0 is a cold start (counted from reset release); every later vector is
a mid-stream change, applied at bit_count == SYNC_BIT_COUNT (24).

MAX_LATENCY is the worst case of the architecture, not a magic number:
    up to 31 cycles waiting for that channel's load slot (tx_shift_reg loads
    each channel once per 32-cycle frame)
  +  8 cycles to serialise the byte
  +  2 cycles (rx byte_done register + tdm_demux output register)
  = 41 cycles
(verified by sweeping all 32 possible bit_count phases: min 34, max 41).
"""

MAX_LATENCY = 41


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
