"""
NDISender — send BGRA/RGBA pixel frames over NDI to any NDI-compatible receiver
(TouchDesigner, OBS, Resolume, VLC, etc.) on the local network.

Usage::

    with NDISender("MySource") as s:
        s.send_frame(ptr, w, h)
"""
import ctypes
from . import _lib
from ._base import _NDIHandle


class NDISender(_NDIHandle):
    """
    Wraps NDIlib_send_* to broadcast BGRA/RGBA video frames over the network.

    Parameters
    ----------
    name : str
        NDI source name visible to receivers on the LAN.
    fps_n, fps_d : int
        Frame-rate numerator/denominator. Default 60/1. Used as metadata
        hint in the frame; actual send rate is determined by how fast frames
        are pushed.
    """

    _destroy_fn = staticmethod(_lib._dll.NDIlib_send_destroy)

    def __init__(self, name: str = "OmniverseViewport", fps_n: int = 60, fps_d: int = 1):
        super().__init__()
        settings = _lib.NDIlib_send_create_t(
            p_ndi_name=_lib._to_cstr(name),
            p_groups=None,
            clock_video=False,
            clock_audio=False,
        )
        self._instance = _lib._dll.NDIlib_send_create(ctypes.byref(settings))
        if not self._instance:
            raise RuntimeError("NDIlib_send_create returned NULL — failed to create NDI sender")
        self._name  = name
        self._fps_n = fps_n
        self._fps_d = fps_d
        # Reused across send_frame calls — only mutating fields are reassigned
        # per frame. Allocating a new struct every send is measurable at 60fps.
        self._frame = _lib.NDIlib_video_frame_v2_t(
            xres=0,
            yres=0,
            FourCC=_lib.FOURCC_BGRA,
            frame_rate_N=fps_n,
            frame_rate_D=fps_d,
            picture_aspect_ratio=0.0,
            frame_format_type=_lib.FRAME_FORMAT_PROGRESSIVE,
            timecode=0,
            p_data=0,
            line_stride_in_bytes=0,
            p_metadata=None,
            timestamp=0,
        )

    # ------------------------------------------------------------------ #

    def send_frame(
        self,
        ptr,
        width: int,
        height: int,
        fourcc: int = _lib.FOURCC_BGRA,
        line_stride: int = 0,
    ):
        """
        Send one video frame.

        Parameters
        ----------
        ptr : int | ctypes.c_void_p
            Raw pointer to the pixel buffer (``height * line_stride`` bytes).
        width, height : int
            Frame dimensions.
        fourcc : int
            Pixel format constant (default FOURCC_BGRA). Use FOURCC_RGBA if
            your buffer is in RGBA order.
        line_stride : int
            Bytes per row. 0 (default) means tightly packed: ``width * 4``.

        Caller-buffer lifetime
        ----------------------
        ``NDIlib_send_send_video_v2`` is synchronous in terms of buffer
        ownership — it returns once NDI has consumed the data from the
        pointer, so the caller can safely mutate or free the buffer right
        after this call returns. The network send itself happens on an
        internal worker thread.
        """
        f = self._frame
        f.xres = width
        f.yres = height
        f.FourCC = fourcc
        f.p_data = int(ptr)
        f.line_stride_in_bytes = line_stride or width * 4
        _lib._dll.NDIlib_send_send_video_v2(self._instance, ctypes.byref(f))

    # ------------------------------------------------------------------ #

    def __repr__(self):
        return f"<NDISender name={self._name!r} fps={self._fps_n}/{self._fps_d}>"
