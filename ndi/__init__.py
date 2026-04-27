"""
NDIForPython — unofficial Python bindings for the NDI® SDK.

Quick start::

    from ndi import NDISender, FOURCC_BGRA

    with NDISender("MySource") as nd:
        nd.send_frame(buf_ptr, width, height, FOURCC_BGRA)

Requires the NDI Runtime to be installed separately
(https://ndi.video/download-ndi-sdk/) — this package does not redistribute
the runtime DLL. Windows x64 only.

NDI® is a registered trademark of Vizrt Group. This project is not
affiliated with, endorsed by, or sponsored by Vizrt or NewTek.
"""
from .sender import NDISender
from ._lib import (
    FOURCC_BGRA,
    FOURCC_RGBA,
    FOURCC_BGRX,
    FRAME_FORMAT_PROGRESSIVE,
)

__all__ = [
    "NDISender",
    "FOURCC_BGRA",
    "FOURCC_RGBA",
    "FOURCC_BGRX",
    "FRAME_FORMAT_PROGRESSIVE",
]
