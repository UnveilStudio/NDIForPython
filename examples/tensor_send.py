"""
tensor_send.py — Send the final image of an inference / generation pipeline
over NDI as uint8 RGBA, zero-copy from NumPy.

Why uint8 and not float? NDI internally encodes/compresses to 8-bit anyway,
so feeding it a higher-precision tensor is wasted work. Convert your float
tensor to uint8 RGBA *once* (typically the last step of your model
post-processing) and hand the buffer directly to NDI — no intermediate copy.

The NDI sender takes a raw pointer to a contiguous RGBA/BGRA buffer.
NumPy arrays already live in a contiguous block of memory, so we hand
NDI the array's address directly via `arr.ctypes.data`.

Run alongside any NDI receiver (TouchDesigner, OBS, Resolume, vMix, …).
The source name is "NDIForPython tensor demo".

Requirements:
    1. NDI Runtime installed: https://ndi.video/download-ndi-sdk/
    2. pip install numpy
    3. pip install git+https://github.com/UnveilStudio/NDIForPython.git
"""
import ctypes
import math
import os
import sys
import time

import numpy as np

# Make the local package importable when running this file directly from a
# clone of the repo (without `pip install`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ndi import NDISender, FOURCC_RGBA

WIDTH, HEIGHT, FPS = 1280, 720, 60
DURATION_S = 30


def main() -> None:
    # NumPy RGBA frame, HWC layout — uint8, contiguous by construction.
    frame = np.empty((HEIGHT, WIDTH, 4), dtype=np.uint8)
    frame[..., 3] = 255                                  # alpha = opaque
    assert frame.flags["C_CONTIGUOUS"], "frame must be C-contiguous"

    # Vectorised gradient bases (precomputed once).
    xs = np.arange(WIDTH,  dtype=np.uint16)
    ys = np.arange(HEIGHT, dtype=np.uint16)[:, None]

    print(f"NDIForPython tensor demo — {WIDTH}x{HEIGHT} @ {FPS} fps (NumPy zero-copy)")
    print("Source name: 'NDIForPython tensor demo'\n")

    with NDISender("NDIForPython tensor demo", fps_n=FPS) as nd:
        deadline = time.perf_counter()
        for frame_idx in range(FPS * DURATION_S):
            t = frame_idx / FPS
            r_off = int((math.sin(t)         * 0.5 + 0.5) * 255)
            g_off = int((math.sin(t * 1.3)   * 0.5 + 0.5) * 255)
            b_off = int((math.sin(t * 0.7)   * 0.5 + 0.5) * 255)

            # Vectorised RGBA gradient — fast enough for 1280x720@60.
            frame[..., 0] = (xs + r_off) & 0xFF          # R
            frame[..., 1] = (ys + g_off) & 0xFF          # G
            frame[..., 2] = ((xs ^ ys) + b_off) & 0xFF   # B
            # alpha already 255

            # Zero-copy: NDI reads directly from NumPy's buffer.
            nd.send_frame(frame.ctypes.data, WIDTH, HEIGHT, FOURCC_RGBA)

            if frame_idx % FPS == 0:
                print(f"  t={t:5.1f}s  frame={frame_idx}")

            deadline += 1 / FPS
            slack = deadline - time.perf_counter()
            if slack > 0:
                time.sleep(slack)
            else:
                deadline = time.perf_counter()           # we fell behind, resync

    print("\nDone.")


# --------------------------------------------------------------------------- #
# PyTorch quick reference (uncomment if you have torch installed)
# --------------------------------------------------------------------------- #
#
# import torch
#
# # tensor: float32 RGB CHW in [0, 1] (typical model output)
# def send_torch_tensor(nd, tensor: torch.Tensor) -> None:
#     chw   = tensor.detach().cpu().clamp(0, 1)
#     hwc   = chw.permute(1, 2, 0).contiguous()
#     uint8 = (hwc * 255).to(torch.uint8).numpy()           # (H, W, 3) uint8
#     # Add an alpha channel — NDI wants 4 channels.
#     rgba  = np.concatenate([uint8, np.full(uint8.shape[:2] + (1,), 255, np.uint8)], axis=-1)
#     rgba  = np.ascontiguousarray(rgba)
#     h, w  = rgba.shape[:2]
#     nd.send_frame(rgba.ctypes.data, w, h, FOURCC_RGBA)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
