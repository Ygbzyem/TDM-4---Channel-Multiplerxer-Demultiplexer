# Verification Report

Generated : 2026-10-22 03:10:16

Input     : `input_vectors.hex`

Reference : Python golden model (`golden_model.TDMGoldenModel`)


Total vectors: 20

Passed: 20

Failed: 0


## Latency (measured in RTL simulation)

- Cold start (vector 0): 33 clocks
- Mid-stream change: min 40 / max 40 clocks
- Allowed maximum: 41 clocks -> PASS

## Per-vector results

| # | Input | RTL CHx_OUT | Bit stream (32 bit) | Latency | Result |
|---|-------|-------------|---------------------|---------|--------|
| 0 | `a53cf05a` | match | match | 33 | PASS |
| 1 | `11223344` | match | match | 40 | PASS |
| 2 | `00ff0180` | match | match | 40 | PASS |
| 3 | `ffffffff` | match | match | 40 | PASS |
| 4 | `00000000` | match | match | 40 | PASS |
| 5 | `a3b1799d` | match | match | 40 | PASS |
| 6 | `1c80317f` | match | match | 40 | PASS |
| 7 | `06671ad1` | match | match | 40 | PASS |
| 8 | `bdd640fb` | match | match | 40 | PASS |
| 9 | `46685257` | match | match | 40 | PASS |
| 10 | `3eb13b90` | match | match | 40 | PASS |
| 11 | `392456de` | match | match | 40 | PASS |
| 12 | `23b8c1e9` | match | match | 40 | PASS |
| 13 | `bc8960a9` | match | match | 40 | PASS |
| 14 | `1a3d1fa7` | match | match | 40 | PASS |
| 15 | `ad3c2d6d` | match | match | 40 | PASS |
| 16 | `bd9c66b3` | match | match | 40 | PASS |
| 17 | `e465e150` | match | match | 40 | PASS |
| 18 | `8b9d2434` | match | match | 40 | PASS |
| 19 | `16419f82` | match | match | 40 | PASS |

Status: PASS
