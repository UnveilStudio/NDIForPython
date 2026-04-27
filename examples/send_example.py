"""
send_example.py — Publish an animated BGRA gradient over NDI at 60 fps.

Run this and open any NDI receiver (TouchDesigner "TOP NDI In", OBS "NDI
Source", VLC, Resolume, vMix, …) on the same LAN. A source named
"NDIForPython demo" should appear within ~1 second.

Press Ctrl+C to stop.

Requirements:
    1. Install the NDI Runtime: https://ndi.video/download-ndi-sdk/
    2. pip install git+https://github.com/UnveilStudio/NDIForPython.git
    3. pip install numpy
"""
import math
import os
import sys
import time

import numpy as np

# Make the local package importable when running this file directly from a
# clone of the repo (without `pip install`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ndi import NDISender, FOURCC_BGRA

WIDTH, HEIGHT = 1280, 720
FPS = 60
DURATION_S = 30


def main() -> None:
    # Vectorised gradient bases — computed once, reused every frame.
    xs = np.arange(WIDTH,  dtype=np.uint16)
    ys = np.arange(HEIGHT, dtype=np.uint16)[:, None]

    bgra = np.empty((HEIGHT, WIDTH, 4), dtype=np.uint8)
    bgra[..., 3] = 255                                   # alpha opaque

    print(f"NDIForPython demo — {WIDTH}x{HEIGHT} @ {FPS} fps (NumPy vectorised)")
    print("Source name: 'NDIForPython demo'")
    print("Open any NDI receiver on the LAN — press Ctrl+C to stop.\n")

    with NDISender("NDIForPython demo", fps_n=FPS) as nd:
        frame_idx = 0
        deadline = time.perf_counter()
        last_log_frame = 0
        last_log_t = deadline

        while frame_idx < FPS * DURATION_S:
            t = frame_idx / FPS
            phase = (math.sin(t * 1.5) * 0.5 + 0.5)
            r_off = int(phase * 255)
            b_off = int((1 - phase) * 255)
            g_off = int((math.cos(t * 0.9) * 0.5 + 0.5) * 255)

            # Whole-frame writes — NumPy broadcasts these in C, no Python
            # per-pixel loop. Plenty of headroom to drive 60 fps at 720p.
            bgra[..., 0] = (xs + b_off) & 0xFF                # B
            bgra[..., 1] = ((xs ^ ys) + g_off) & 0xFF         # G
            bgra[..., 2] = (ys + r_off) & 0xFF                # R
            # alpha already 255

            nd.send_frame(bgra.ctypes.data, WIDTH, HEIGHT, FOURCC_BGRA)

            if frame_idx - last_log_frame >= FPS:
                now = time.perf_counter()
                achieved = (frame_idx - last_log_frame) / (now - last_log_t)
                print(f"  t={t:5.1f}s  frame={frame_idx:5d}  achieved={achieved:5.1f} fps")
                last_log_frame = frame_idx
                last_log_t = now

            frame_idx += 1
            deadline += 1 / FPS
            slack = deadline - time.perf_counter()
            if slack > 0:
                time.sleep(slack)
            else:
                deadline = time.perf_counter()                # fell behind, resync

    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
