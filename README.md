# NDIForPython

Python bindings for [NDI®](https://ndi.video) — real-time, low-latency video
streaming over standard IP networks.
Lets a Python process publish video frames to any NDI-aware application
(TouchDesigner, OBS, Resolume, vMix, VLC, Notch, Unreal, Unity, …) on the
same LAN.

> **Disclaimer.** This is an **unofficial third-party binding**. NDI® is a
> registered trademark of **Vizrt Group**. This project is not affiliated
> with, endorsed by, or sponsored by Vizrt or NewTek.
> See [`NDI_NOTICE.md`](NDI_NOTICE.md).

**Windows x64 only** at the moment (`Processing.NDI.Lib.x64.dll`).
Linux/macOS support is feasible but not implemented yet — PRs welcome.

---

## ⚠️ You must install the NDI Runtime first

This package does **NOT** include the NDI DLL. Vizrt's licence does not allow
us to bundle it, so you grab it directly from them — it's free.

1. Go to **https://ndi.video/download-ndi-sdk/**
2. Download and install **"NDI 6 Tools"** (or "NDI 6 Runtime" if you only
   need to run NDI clients) — NDI 5 also works.
3. That's it. The installer drops `Processing.NDI.Lib.x64.dll` in:
   ```
   C:\Program Files\NDI\NDI 6 Runtime\v6\
   ```
   (or `NDI 5 Runtime\v5\`, or `NDI 6 SDK\Lib\x64\`). NDIForPython auto-detects
   all of these. It also honours the `NDI_RUNTIME_DIR_V6` /
   `NDI_RUNTIME_DIR_V5` env vars set by the installer.

If you `import ndi` without the runtime installed, you get a clear error
pointing you back here.

## Install

```bash
pip install git+https://github.com/UnveilStudio/NDIForPython.git
```

That's all — no compiler, no SDK, no bundled binaries. Just Python +
`ctypes` against the runtime DLL you already installed in the step above.

## Quick start — send a video frame

```python
import ctypes, time, math
from ndi import NDISender, FOURCC_BGRA

W, H, FPS = 1280, 720, 60
buf = (ctypes.c_ubyte * (W * H * 4))()                # raw BGRA buffer

with NDISender("MyPythonSource", fps_n=FPS) as nd:
    for frame in range(FPS * 10):                     # 10 seconds
        # write something into buf — here a moving gradient
        t = frame / FPS
        offs = int((math.sin(t) * 0.5 + 0.5) * 255)
        for i in range(0, len(buf), 4):
            buf[i+0] = (i // 4) % 256                 # B
            buf[i+1] = ((i // 4) + offs) % 256        # G
            buf[i+2] = offs                           # R
            buf[i+3] = 255                            # A
        nd.send_frame(ctypes.addressof(buf), W, H, FOURCC_BGRA)
        time.sleep(1 / FPS)
```

In TouchDesigner / OBS / VLC, add an **NDI source** and you'll see
`MyPythonSource` appear on the network within a second.

See [`examples/send_example.py`](examples/send_example.py) for a runnable
animated gradient sender.

## Receiver?

Not implemented yet — the current package is sender-only. Receiver is on the
roadmap; PRs welcome (the NDI receive API is a flat C API too, the binding
shape will mirror `NDISender`).

## How it works

```
Application
    ↓
ndi.sender.NDISender                        ← thin Python class
    ↓
ndi._lib (ctypes function bindings)         ← FOURCC, structs, NDIlib_*
    ↓
Processing.NDI.Lib.x64.dll                  ← NDI Runtime (you install it)
    ↓
NDI mDNS discovery + RTP-like transport     ← Vizrt's protocol over LAN
```

The NDI C API is a flat set of exported functions (no COM/vtable), so the
binding is straightforward: `ctypes.CDLL`, struct definitions, and a
one-time `NDIlib_initialize()` at import time.

## Pixel-format note

`send_frame` defaults to **BGRA** (the most common NDI format). If your
buffer is in RGBA order, pass `fourcc=FOURCC_RGBA`. Stride is assumed to
be `width * 4` (tightly packed, no padding).

## Performance tips

- **Reuse the buffer.** Allocating `(c_ubyte * size)()` per frame at 60 fps
  is wasteful. Allocate once outside the loop and write into it.
- **`send_frame` is non-blocking.** It hands the frame to NDI's worker
  thread and returns immediately. NDI handles network throttling internally.
- **For NumPy / PyTorch tensors**, use `tensor.contiguous()` then
  `(c_ubyte * size).from_buffer(arr)` to get a zero-copy view. Make sure the
  array is `uint8` and BGRA-ordered (or pass `FOURCC_RGBA`).

## Support this project

If `NDIForPython` saves you time or makes its way into something cool, you
can throw a beer 🍺 at the maintainer:

- 🟧 **Patreon** — [patreon.com/unveil_studio](https://www.patreon.com/unveil_studio)
- 💸 **PayPal** — [paypal.me/Unveilstudio](https://paypal.me/Unveilstudio)

Every tip is genuinely appreciated and goes straight into keeping this and
similar tools alive.

## License

This project is released under the **MIT License** — see [`LICENSE`](LICENSE).

The NDI® Runtime is **not** part of this project and is governed by the
**NDI SDK Licence Agreement** between you and **Vizrt**. See
[`NDI_NOTICE.md`](NDI_NOTICE.md) for the trademark notice and the link to
the official Runtime download.
