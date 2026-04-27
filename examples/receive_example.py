"""
receive_example.py — Discover NDI sources on the LAN and pull video frames.

Usage:
    python examples/receive_example.py                       # auto-pick first source
    python examples/receive_example.py "MACHINE (Source)"    # connect to a specific one

The script prints frame info every second and drops the data on the floor.
Replace the inner loop with your own processing (numpy, model inference,
display, etc.).

Requirements:
    1. NDI Runtime installed: https://ndi.video/download-ndi-sdk/
    2. pip install git+https://github.com/UnveilStudio/NDIForPython.git

Tip: run examples/send_example.py from the same machine first if you want
something to receive.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ndi import NDISourceFinder, NDIReceiver


def main() -> int:
    requested = sys.argv[1] if len(sys.argv) > 1 else None

    print("Discovering NDI sources on the LAN (2 s)...")
    with NDISourceFinder(show_local_sources=True) as finder:
        sources = finder.wait(timeout_ms=2000)

    if not sources:
        print("No NDI sources found. Is your sender running?")
        return 1

    print(f"Found {len(sources)} source(s):")
    for s in sources:
        print(f"  - {s}")

    if requested is None:
        target = sources[0]
        print(f"\nNo source name passed — connecting to the first one: {target!r}")
    elif requested in sources:
        target = requested
    else:
        print(f"\nRequested source {requested!r} not in the discovered list.")
        return 2

    print(f"\nConnecting to {target!r}...")
    frame_count = 0
    last_log = time.perf_counter()

    with NDIReceiver(target, connect_timeout_ms=5000) as rx:
        print("Connected. Pulling frames — Ctrl+C to stop.\n")
        while True:
            with rx.receive(timeout_ms=200) as frame:
                if not frame:
                    # Either no frame yet (just connected) or sender stalled.
                    continue
                frame_count += 1
                now = time.perf_counter()
                if now - last_log >= 1.0:
                    fps = frame_count / (now - last_log)
                    print(
                        f"  {frame.width}x{frame.height}  "
                        f"stride={frame.line_stride}  "
                        f"fps={fps:5.1f}  "
                        f"sender_fps={frame.fps_n}/{frame.fps_d}"
                    )
                    frame_count = 0
                    last_log = now


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        print("\nStopped by user.")
