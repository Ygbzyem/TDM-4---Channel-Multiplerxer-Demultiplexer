FRAME_BITS = 32


def check_frame_length(stream, verbose=True):
    """A TDM frame is 4 channels x 8 bits = 32 bits on the serial line."""

    actual_length = len(stream)
    ok = (actual_length == FRAME_BITS)

    if verbose:
        print("\n=== FRAME LENGTH CHECK ===")
        print(f"Expected Length : {FRAME_BITS} bits")
        print(f"Actual Length   : {actual_length} bits")
        print("PASS" if ok else "FAIL")

    return ok
