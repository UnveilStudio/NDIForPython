"""
send_example.py — Publish an animated BGRA gradient over NDI.

Run this and open any NDI receiver (TouchDesigner "TOP NDI In", OBS "NDI
Source", VLC, Resolume, vMix, …) on the same LAN. A source named
"NDIForPython demo" should appear within ~1 second.

Press Ctrl+C to stop.

Requirements:
    1. Install the NDI Runtime: https://ndi.video/download-ndi-sdk/
    2. pip install git+https://github.com/UnveilStudio/NDIForPython.git
"""
import ctypes
import math
import sys
import os
import time

# Make the local package importable when running this file directly from a
# clone of the repo (without `pip install`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ndi import NDISender, FOURCC_BGRA

WIDTH, HEIGHT = 1280, 720
FPS = 60
DURATION_S = 30


def main() -> None:
    pixel_count = WIDTH * HEIGHT
    buffer_size = pixel_count * 4
    buf = (ctypes.c_ubyte * buffer_size)()           # allocate ONCE
    buf_ptr = ctypes.addressof(buf)

    print(f"NDIForPython demo — {WIDTH}x{HEIGHT} @ {FPS} fps")
    print("Source name: 'NDIForPython demo'")
    print("Open any NDI receiver on the LAN — press Ctrl+C to stop.\n")

    with NDISender("NDIForPython demo", fps_n=FPS) as nd:
        frame_idx = 0
        deadline = time.perf_counter()
        while frame_idx < FPS * DURATION_S:
            t = frame_idx / FPS
            phase = (math.sin(t * 1.5) * 0.5 + 0.5)
            r_off = int(phase * 255)
            b_off = int((1 - phase) * 255)

            # Cheap moving gradient — a row stride pattern, no per-pixel python loop.
            ctypes.memset(buf_ptr, 0, buffer_size)
            for y in range(0, HEIGHT, 8):                 # one stripe every 8 rows
                row_offset = y * WIDTH * 4
                for x in range(WIDTH):
                    i = row_offset + x * 4
                    buf[i + 0] = (x + b_off) & 0xFF        # B
                    buf[i + 1] = (x ^ y) & 0xFF            # G
                    buf[i + 2] = (y + r_off) & 0xFF        # R
                    buf[i + 3] = 255                       # A

            nd.send_frame(buf_ptr, WIDTH, HEIGHT, FOURCC_BGRA)

            if frame_idx % FPS == 0:
                print(f"  t={t:5.1f}s  frame={frame_idx}")

            frame_idx += 1
            deadline += 1 / FPS
            slack = deadline - time.perf_counter()
            if slack > 0:
                time.sleep(slack)
            else:
                deadline = time.perf_counter()        # we fell behind, resync

    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
