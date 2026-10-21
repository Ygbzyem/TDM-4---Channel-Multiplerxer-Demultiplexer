from datetime import datetime


def write_report(path, summary):
    """Write verification_report.md from REAL results.

    summary keys: input_file, results (list of per-vector dicts), latency
    (dict from latency_checker.check_latency), all_pass (bool).
    """

    results = summary["results"]
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    lat = summary["latency"]

    lines = []
    lines.append("# Verification Report\n")
    lines.append(f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"Input     : `{summary['input_file']}`\n")
    lines.append("Reference : Python golden model (`golden_model.TDMGoldenModel`)\n")
    lines.append("")
    lines.append(f"Total vectors: {total}\n")
    lines.append(f"Passed: {passed}\n")
    lines.append(f"Failed: {total - passed}\n")
    lines.append("")
    lines.append("## Latency (measured in RTL simulation)\n")
    lines.append(f"- Cold start (vector 0): {lat['cold_start']} clocks")
    lines.append(f"- Mid-stream change: min {lat['steady_min']} / max {lat['steady_max']} clocks")
    lines.append(f"- Allowed maximum: {lat['max_allowed']} clocks -> {'PASS' if lat['ok'] else 'FAIL'}\n")
    lines.append("## Per-vector results\n")
    lines.append("| # | Input | RTL CHx_OUT | Bit stream (32 bit) | Latency | Result |")
    lines.append("|---|-------|-------------|---------------------|---------|--------|")
    for r in results:
        stream = "match" if r["stream_ok"] else f"mismatch @ cycle {r['bad_cycle']}"
        out = "match" if r["out_ok"] else f"mismatch ({r['rtl_out']})"
        lines.append(
            f"| {r['index']} | `{r['input']}` | {out} | {stream} | "
            f"{r['latency']} | {'PASS' if r['ok'] else 'FAIL'} |"
        )
    lines.append("")
    lines.append(f"Status: {'PASS' if summary['all_pass'] else 'FAIL'}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
