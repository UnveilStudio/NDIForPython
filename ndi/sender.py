"""
NDISender — send BGRA/RGBA pixel frames over NDI to any NDI-compatible receiver
(TouchDesigner, OBS, Resolume, VLC, etc.) on the local network.

Usage::

    from ndi.sender import NDISender

    sender = NDISender("OmniverseViewport")
    # ptr: raw c_void_p pointer to a BGRA pixel buffer (width * height * 4 bytes)
    sender.send_frame(ptr, 1920, 1080)
    sender.release()

Or as a context manager::

    with NDISender("MySource") as s:
        s.send_frame(ptr, w, h)
"""
import ctypes
from . import _lib


class NDISender:
    """
    Wraps NDIlib_send_* to broadcast BGRA video frames over the network.

    Parameters
    ----------
    name : str
        NDI source name visible to receivers on the LAN.
    fps_n, fps_d : int
        Frame-rate numerator/denominator. Default 60/1. Used only as metadata
        hint in the frame; actual send rate is determined by how fast frames
        are pushed.
    """

    def __init__(self, name: str = "OmniverseViewport", fps_n: int = 60, fps_d: int = 1):
        settings = _lib.NDIlib_send_create_t(
            p_ndi_name=name.encode(),
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

    # ------------------------------------------------------------------ #

    def send_frame(
        self,
        ptr,
        width: int,
        height: int,
        fourcc: int = _lib.FOURCC_BGRA,
        fps_n: int = 0,
        fps_d: int = 0,
    ):
        """
        Send one video frame.

        Parameters
        ----------
        ptr : int | ctypes.c_void_p
            Raw pointer to the pixel buffer (width * height * 4 bytes, BGRA).
            Can be an integer address or a ctypes c_void_p.
        width, height : int
            Frame dimensions.
        fourcc : int
            Pixel format constant (default FOURCC_BGRA). Use FOURCC_RGBA if
            your buffer is in RGBA order.
        fps_n, fps_d : int
            Override frame-rate hint for this frame. 0 = use sender default.
        """
        frame = _lib.NDIlib_video_frame_v2_t(
            xres=width,
            yres=height,
            FourCC=fourcc,
            frame_rate_N=fps_n or self._fps_n,
            frame_rate_D=fps_d or self._fps_d,
            picture_aspect_ratio=0.0,        # auto (xres/yres)
            frame_format_type=_lib.FRAME_FORMAT_PROGRESSIVE,
            timecode=0,                       # synthesize
            p_data=int(ptr),
            line_stride_in_bytes=width * 4,
            p_metadata=None,
            timestamp=0,                      # synthesize
        )
        _lib._dll.NDIlib_send_send_video_v2(self._instance, ctypes.byref(frame))

    # ------------------------------------------------------------------ #

    def release(self):
        """Destroy the sender and free NDI resources."""
        if self._instance:
            _lib._dll.NDIlib_send_destroy(self._instance)
            self._instance = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release()

    def __del__(self):
        self.release()

    def __repr__(self):
        return f"<NDISender name={self._name!r} fps={self._fps_n}/{self._fps_d}>"
