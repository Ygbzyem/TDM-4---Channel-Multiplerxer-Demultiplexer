"""Random test vectors for the RTL regression.

  python golden_model/random_regression.py --n 200 --seed 42
  python golden_model/random_regression.py --n 200 --channels 8 --width 16

writes input/random_vectors.hex for 4 x 8, or input/random_vectors_<N>x<W>.hex
for any other size: one packed {CH0, CH1, ..., CH(N-1)} hex word of N*W bits per
line, same format as input_vectors.hex. Feed it to the RTL and compare with the
golden model:

  python golden_model/run_verification.py --vectors input/random_vectors.hex
  python golden_model/run_verification.py --vectors input/random_vectors_8x16.hex --channels 8 --width 16

The testbench holds at most MAX_VECTORS = 256 vectors.
run_random_tests() below is only a self-test of the golden model itself
(serialize -> deserialize); it never touches the RTL.
"""

import argparse
import random
from pathlib import Path

from golden_model import TDMGoldenModel

ROOT = Path(__file__).resolve().parent.parent
MAX_VECTORS = 256


def default_out(num_channels=4, data_width=8):
    name = "random_vectors.hex" if (num_channels, data_width) == (4, 8) \
        else f"random_vectors_{num_channels}x{data_width}.hex"
    return ROOT / "input" / name


def generate_vectors(n, seed, path, num_channels=4, data_width=8):
    rng = random.Random(seed)
    bits = num_channels * data_width
    words = [rng.getrandbits(bits) for _ in range(n)]
    digits = -(-bits // 4)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    order = ",".join(f"CH{i}" for i in range(num_channels))
    with open(path, "w") as f:
        f.write(f"// {n} random vectors, seed={seed}, {num_channels} x {data_width}, format {{{order}}}\n")
        for w in words:
            f.write(f"{w:0{digits}x}\n")
    return path


def run_random_tests(total_tests=1000, num_channels=4, data_width=8):
    """Golden-model self test (no RTL involved)."""

    gm = TDMGoldenModel(num_channels, data_width)

    print("\n=== GOLDEN MODEL SELF-TEST (random) ===")

    for test_no in range(total_tests):
        chs = [random.getrandbits(data_width) for _ in range(num_channels)]
        if gm.run_frame(*chs)["outputs"] != chs:
            print(f"FAIL @ Test {test_no}")
            return False

    print(f"PASS ({total_tests} tests)")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().split("\n")[0])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--channels", type=int, default=4, help="NUM_CHANNELS (default 4)")
    ap.add_argument("--width", type=int, default=8, help="DATA_WIDTH (default 8)")
    ap.add_argument("--out", default=None, help="output file (default input/random_vectors[_NxW].hex)")
    a = ap.parse_args()

    if not 1 <= a.n <= MAX_VECTORS:
        raise SystemExit(f"--n must be between 1 and {MAX_VECTORS} (testbench MAX_VECTORS)")
    out = a.out or default_out(a.channels, a.width)
    print(f"Wrote {a.n} vectors to {generate_vectors(a.n, a.seed, out, a.channels, a.width)}")
