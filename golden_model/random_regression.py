import argparse
import random
from pathlib import Path

from golden_model import TDMGoldenModel

ROOT = Path(__file__).resolve().parent.parent
MAX_VECTORS = 256


def generate_vectors(n, seed, path):
    rng = random.Random(seed)
    words = [rng.getrandbits(32) for _ in range(n)]

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(f"// {n} random vectors, seed={seed}, format {{CH0,CH1,CH2,CH3}}\n")
        for w in words:
            f.write(f"{w:08x}\n")
    return path


def run_random_tests(total_tests=1000):
    """Golden-model self test (no RTL involved)."""

    gm = TDMGoldenModel()

    print("\n=== GOLDEN MODEL SELF-TEST (random) ===")

    for test_no in range(total_tests):
        chs = [random.randint(0, 255) for _ in range(4)]
        result = gm.run_frame(*chs)
        got = [result["ch0_out"], result["ch1_out"], result["ch2_out"], result["ch3_out"]]

        if got != chs:
            print(f"FAIL @ Test {test_no}")
            return False

    print(f"PASS ({total_tests} tests)")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(ROOT / "input" / "random_vectors.hex"))
    a = ap.parse_args()

    if not 1 <= a.n <= MAX_VECTORS:
        raise SystemExit(f"--n must be between 1 and {MAX_VECTORS} (testbench MAX_VECTORS)")

    print(f"Wrote {a.n} vectors to {generate_vectors(a.n, a.seed, a.out)}")
