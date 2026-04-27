# AGENTS.md — Quick guide for AI agents

This file helps an AI agent (Claude Code, Cursor, Copilot, …) use
`NDIForPython` correctly on the first try.

## TL;DR

- `NDIForPython` exposes one class today: `NDISender`. Import path:
  `from ndi import NDISender, FOURCC_BGRA, FOURCC_RGBA`.
- It's a `ctypes` wrapper over `Processing.NDI.Lib.x64.dll` (NDI Runtime).
- **Windows x64 only** — `import ndi` raises `OSError` on other platforms.
- **The DLL is NOT bundled** — the user must install the NDI Runtime
  themselves from https://ndi.video. We may not redistribute it for
  licensing reasons.
- Pixel format defaults to **BGRA** (NDI's most common). RGBA also supported
  via `fourcc=FOURCC_RGBA`. Stride is `width * 4`, tightly packed.

## Installation (what to tell the user)

1. Install the NDI Runtime: https://ndi.video/download-ndi-sdk/ →
   "NDI 6 Tools" (or 5). Default install path is fine.
2. `pip install git+https://github.com/UnveilStudio/NDIForPython.git`

If `import ndi` fails with
*"Processing.NDI.Lib.x64.dll not found"*, step 1 was skipped or the
runtime is in a non-standard location. Set
`NDI_RUNTIME_DIR_V6=C:\path\to\NDI\runtime\v6\` and retry.

## Sender pattern

```python
import ctypes
from ndi import NDISender, FOURCC_BGRA

W, H, FPS = 1920, 1080, 60
buf = (ctypes.c_ubyte * (W * H * 4))()       # allocate ONCE

with NDISender("MySource", fps_n=FPS) as nd:
    while running:
        write_pixels_into(buf)               # your code, BGRA-ordered
        nd.send_frame(ctypes.addressof(buf), W, H, FOURCC_BGRA)
```

Notes:
- Reuse `buf` between frames — do not re-allocate per frame.
- `send_frame` accepts an integer address OR a `ctypes.c_void_p`.
- `send_frame` is non-blocking — NDI hands off to a worker thread internally.
- Use the context manager (`with ... as`) so `NDIlib_send_destroy` runs.

## NumPy / PyTorch zero-copy

```python
import numpy as np, ctypes
from ndi import NDISender, FOURCC_RGBA

arr = np.empty((H, W, 4), dtype=np.uint8)    # RGBA HWC
buf = (ctypes.c_ubyte * arr.size).from_buffer(arr)
nd.send_frame(ctypes.addressof(buf), W, H, FOURCC_RGBA)
```

For PyTorch, `tensor.detach().cpu().contiguous().numpy()` first.

## Things to NOT do

- **Do not bundle `Processing.NDI.Lib.x64.dll` with this package.** Vizrt's
  NDI SDK Licence forbids it. Always require the user to install the
  Runtime separately. This is non-negotiable — see `NDI_NOTICE.md`.
- **Do not call `NDIlib_initialize()` manually.** `_lib.py` does it once at
  import time. Calling it again is harmless but pointless.
- **Do not pass an unaligned / non-contiguous buffer** — `line_stride_in_bytes`
  is hard-coded to `width * 4` in `send_frame`. If you have padded rows,
  you'd need to extend the binding to expose stride.
- **Do not use NDI to send sensitive content over an untrusted LAN.** NDI is
  cleartext on the wire. There is `NDI HX` and TLS-capable variants, but
  this binding only does the standard, in-the-clear sender.

## Adding a Receiver (roadmap)

The receiver is not implemented yet. To add it: bind
`NDIlib_find_*` (mDNS discovery) and `NDIlib_recv_*` (frame pull) in
`_lib.py`, then add a `receiver.py` that mirrors the shape of `sender.py`.
Use a polling model (`recv_capture_v2` with a small timeout) for the
public API.

## References

- NDI official site: https://ndi.video
- NDI SDK docs: https://docs.ndi.video/
- This repo: https://github.com/UnveilStudio/NDIForPython
