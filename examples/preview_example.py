"""
preview_example.py — Discover an NDI source and show it in an OpenCV window.

Usage:
    python examples/preview_example.py                       # auto-pick first source
    python examples/preview_example.py "MACHINE (Source)"    # connect to a specific one

Press 'q' or ESC in the preview window to quit.

Requirements:
    1. NDI Runtime installed: https://ndi.video/download-ndi-sdk/
    2. pip install opencv-python numpy
    3. pip install git+https://github.com/UnveilStudio/NDIForPython.git

Tip: run examples/send_example.py from the same machine first if you want
something to receive.
"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ndi import NDISourceFinder, NDIReceiver

WINDOW = "NDIForPython preview"


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
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    last_log = time.perf_counter()
    frame_count = 0

    with NDIReceiver(target, connect_timeout_ms=5000) as rx:
        print("Connected. Showing frames — press 'q' or ESC in the window to quit.\n")
        while True:
            with rx.receive(timeout_ms=200) as frame:
                if not frame:
                    # Even with no frame we must pump the cv2 event loop, or
                    # the window stops repainting.
                    if cv2.waitKey(1) in (ord("q"), 27):
                        break
                    continue

                # Default colour format is BGRX_BGRA → already BGR-ordered for
                # cv2 (the alpha channel is in the 4th byte). Drop stride
                # padding columns and the alpha channel for display.
                view = frame.as_numpy()[:, :frame.width, :3]   # (H, W, 3) BGR
                # Materialise BEFORE the frame is released by the `with` exit.
                bgr  = np.ascontiguousarray(view)

                cv2.imshow(WINDOW, bgr)
                key = cv2.waitKey(1)
                if key in (ord("q"), 27):
                    break

                frame_count += 1
                now = time.perf_counter()
                if now - last_log >= 1.0:
                    fps = frame_count / (now - last_log)
                    sys.stdout.write(
                        f"\r  {frame.width}x{frame.height}  "
                        f"recv={fps:5.1f} fps  "
                        f"sender={frame.fps_n}/{frame.fps_d} "
                    )
                    sys.stdout.flush()
                    frame_count = 0
                    last_log = now

    cv2.destroyAllWindows()
    print("\nClosed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        print("\nStopped by user.")
