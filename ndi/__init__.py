"""
NDIForPython — unofficial Python bindings for the NDI® SDK.

Quick start (sender)::

    from ndi import NDISender, FOURCC_BGRA

    with NDISender("MySource") as nd:
        nd.send_frame(buf_ptr, width, height, FOURCC_BGRA)

Quick start (receiver)::

    from ndi import NDISourceFinder, NDIReceiver

    with NDISourceFinder() as f:
        names = f.wait(timeout_ms=2000)
        print("sources on the LAN:", names)

    with NDIReceiver(names[0]) as rx:
        with rx.receive(timeout_ms=33) as frame:
            if frame is not None:
                arr = frame.as_numpy()      # (H, W_padded, 4) uint8

Requires the NDI Runtime to be installed separately
(https://ndi.video/download-ndi-sdk/) — this package does not redistribute
the runtime DLL. Windows x64 only.

NDI® is a registered trademark of Vizrt Group. This project is not
affiliated with, endorsed by, or sponsored by Vizrt or NewTek.
"""
from .sender   import NDISender
from .finder   import NDISourceFinder
from .receiver import (
    NDIReceiver,
    NDIVideoFrame,
    RECV_COLOR_BGRX_BGRA,
    RECV_COLOR_RGBX_RGBA,
    RECV_COLOR_FASTEST,
    RECV_COLOR_BEST,
    RECV_BANDWIDTH_LOWEST,
    RECV_BANDWIDTH_HIGHEST,
)
from ._lib import (
    FOURCC_BGRA,
    FOURCC_BGRX,
    FOURCC_RGBA,
    FOURCC_RGBX,
    FRAME_FORMAT_PROGRESSIVE,
)

__all__ = [
    # Sender
    "NDISender",
    # Receiver
    "NDISourceFinder",
    "NDIReceiver",
    "NDIVideoFrame",
    # FourCC pixel formats
    "FOURCC_BGRA",
    "FOURCC_BGRX",
    "FOURCC_RGBA",
    "FOURCC_RGBX",
    # Frame format
    "FRAME_FORMAT_PROGRESSIVE",
    # Receiver knobs
    "RECV_COLOR_BGRX_BGRA",
    "RECV_COLOR_RGBX_RGBA",
    "RECV_COLOR_FASTEST",
    "RECV_COLOR_BEST",
    "RECV_BANDWIDTH_LOWEST",
    "RECV_BANDWIDTH_HIGHEST",
]
