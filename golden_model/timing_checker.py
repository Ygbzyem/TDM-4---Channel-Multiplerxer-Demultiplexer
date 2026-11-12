FRAME_BITS = 32                  # default design: 4 channels x 8 bits


def check_frame_length(stream, verbose=True, frame_bits=FRAME_BITS):
    """A TDM frame is NUM_CHANNELS x DATA_WIDTH bits on the serial line (32 for 4 x 8)."""

    actual_length = len(stream)
    ok = (actual_length == frame_bits)

    if verbose:
        print("\n=== FRAME LENGTH CHECK ===")
        print(f"Expected Length : {frame_bits} bits")
        print(f"Actual Length   : {actual_length} bits")
        print("PASS" if ok else "FAIL")

    return ok
