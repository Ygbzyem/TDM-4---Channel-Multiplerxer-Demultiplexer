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
