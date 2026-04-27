"""
send_example.py — Publish the Unveil logo (or a fallback gradient) over NDI.

By default this sends the bundled `assets/unveil_logo.png` at 60 fps so any
NDI receiver on the LAN — `examples/preview_example.py`, TouchDesigner
"TOP NDI In", OBS "NDI Source", VLC, Resolume, vMix, … — can pick it up
under the source name "NDIForPython demo".

If the asset isn't present (e.g. you cloned without the assets/ folder), it
falls back to an animated gradient so the example still shows something.

Press Ctrl+C to stop.

Requirements:
    1. Install the NDI Runtime: https://ndi.video/download-ndi-sdk/
    2. pip install git+https://github.com/UnveilStudio/NDIForPython.git
    3. pip install numpy pillow
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
LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "unveil_logo.png",
)


def _try_load_logo_frame(path: str, w: int, h: int) -> np.ndarray | None:
    """Return a BGRA H×W×4 uint8 frame with the logo letterboxed onto a
    black canvas, or None if PIL/the asset isn't available."""
    try:
        from PIL import Image
    except ImportError:
        print("(Pillow not installed — falling back to gradient)")
        return None
    if not os.path.exists(path):
        print(f"(asset not found: {path} — falling back to gradient)")
        return None

    img = Image.open(path).convert("RGBA")
    # Fit-and-letterbox onto WxH while preserving aspect ratio.
    src_w, src_h = img.size
    scale = min(w / src_w, h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    rgba = np.array(img)                                  # (h_, w_, 4) RGBA
    canvas = np.zeros((h, w, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    off_y = (h - new_h) // 2
    off_x = (w - new_w) // 2
    canvas[off_y:off_y + new_h, off_x:off_x + new_w] = rgba

    # Convert RGBA -> BGRA for NDI by swapping R and B channels.
    bgra = canvas[..., [2, 1, 0, 3]].copy()              # contiguous BGRA
    return bgra


def _gradient_frame(w: int, h: int) -> tuple[np.ndarray, callable]:
    """Return (bgra, animate_inplace) for the fallback animated gradient."""
    xs = np.arange(w, dtype=np.uint16)
    ys = np.arange(h, dtype=np.uint16)[:, None]
    bgra = np.empty((h, w, 4), dtype=np.uint8)
    bgra[..., 3] = 255

    def animate(t: float) -> None:
        phase = math.sin(t * 1.5) * 0.5 + 0.5
        r_off = int(phase * 255)
        g_off = int((math.cos(t * 0.9) * 0.5 + 0.5) * 255)
        b_off = int((1 - phase) * 255)
        bgra[..., 0] = (xs + b_off) & 0xFF                # B
        bgra[..., 1] = ((xs ^ ys) + g_off) & 0xFF         # G
        bgra[..., 2] = (ys + r_off) & 0xFF                # R

    return bgra, animate


def main() -> None:
    bgra = _try_load_logo_frame(LOGO_PATH, WIDTH, HEIGHT)
    if bgra is not None:
        animate = lambda t: None                          # static frame
        mode = f"logo from {os.path.basename(LOGO_PATH)}"
    else:
        bgra, animate = _gradient_frame(WIDTH, HEIGHT)
        mode = "animated gradient (fallback)"

    print(f"NDIForPython demo — {WIDTH}x{HEIGHT} @ {FPS} fps  [{mode}]")
    print("Source name: 'NDIForPython demo'")
    print("Open any NDI receiver on the LAN — press Ctrl+C to stop.\n")

    with NDISender("NDIForPython demo", fps_n=FPS) as nd:
        frame_idx = 0
        deadline = time.perf_counter()
        last_log_frame = 0
        last_log_t = deadline

        while frame_idx < FPS * DURATION_S:
            animate(frame_idx / FPS)
            nd.send_frame(bgra.ctypes.data, WIDTH, HEIGHT, FOURCC_BGRA)

            if frame_idx - last_log_frame >= FPS:
                now = time.perf_counter()
                achieved = (frame_idx - last_log_frame) / (now - last_log_t)
                print(f"  t={frame_idx / FPS:5.1f}s  frame={frame_idx:5d}  "
                      f"achieved={achieved:5.1f} fps")
                last_log_frame = frame_idx
                last_log_t = now

            frame_idx += 1
            deadline += 1 / FPS
            slack = deadline - time.perf_counter()
            if slack > 0:
                time.sleep(slack)
            else:
                deadline = time.perf_counter()

    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
