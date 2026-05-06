"""
NDIReceiver — connect to an NDI sender and pull video frames.

Usage::

    from ndi import NDIReceiver

    # Block up to 5 seconds while NDI discovers the source on the LAN.
    with NDIReceiver("MACHINE-NAME (My Source)", connect_timeout_ms=5000) as rx:
        while running:
            with rx.receive(timeout_ms=33) as frame:
                if not frame:
                    continue
                # frame.width, frame.height, frame.fourcc, frame.data_ptr
                # frame.copy_to(buffer)              — copy into a bytearray
                # frame.as_numpy()                   — zero-copy NumPy view
                process(frame)
"""
import ctypes

from . import _lib
from ._base import _NDIHandle

# NumPy is optional — only NDIVideoFrame.as_numpy() needs it.
try:
    import numpy as _np
except ImportError:
    _np = None

# Re-exported here for convenience so users don't need to also import _lib.
RECV_COLOR_BGRX_BGRA  = _lib.RECV_COLOR_BGRX_BGRA
RECV_COLOR_RGBX_RGBA  = _lib.RECV_COLOR_RGBX_RGBA
RECV_COLOR_FASTEST    = _lib.RECV_COLOR_FASTEST
RECV_COLOR_BEST       = _lib.RECV_COLOR_BEST

RECV_BANDWIDTH_LOWEST  = _lib.RECV_BANDWIDTH_LOWEST
RECV_BANDWIDTH_HIGHEST = _lib.RECV_BANDWIDTH_HIGHEST


# --------------------------------------------------------------------------- #
# Frame wrapper
# --------------------------------------------------------------------------- #

class NDIVideoFrame:
    """
    A single video frame received from the network.

    The underlying pixel buffer is owned by NDI and remains valid only until
    :meth:`release` is called. Use this class as a context manager (the
    receiver returns it inside one) so the frame is always released after
    use, even on exception.

    Attributes
    ----------
    width, height : int
    fourcc : int
        See ``ndi.FOURCC_BGRA`` / ``FOURCC_BGRX`` / ``FOURCC_RGBA``.
    line_stride : int
        Bytes per row, often == ``width * 4`` but may be larger (alignment).
    fps_n, fps_d : int
        Frame-rate numerator / denominator from the sender.
    data_ptr : int
        Raw pointer to the pixel buffer (use with ``ctypes.string_at`` or
        :meth:`as_numpy`).
    """

    __slots__ = ("_recv", "_video", "width", "height", "fourcc",
                 "line_stride", "fps_n", "fps_d", "data_ptr")

    def __init__(self, recv_handle: int, video_struct: _lib.NDIlib_video_frame_v2_t):
        self._recv  = recv_handle
        self._video = video_struct
        self.width        = video_struct.xres
        self.height       = video_struct.yres
        self.fourcc       = video_struct.FourCC
        self.line_stride  = video_struct.line_stride_in_bytes
        self.fps_n        = video_struct.frame_rate_N
        self.fps_d        = video_struct.frame_rate_D
        self.data_ptr     = video_struct.p_data

    # ------------------------------------------------------------------ #

    def copy_to(self, buffer) -> None:
        """
        Copy the pixel data into a caller-provided bytearray / ctypes buffer.

        The destination must be at least ``height * line_stride`` bytes.
        """
        size = self.height * self.line_stride
        if len(buffer) < size:
            raise ValueError(
                f"destination buffer too small: have {len(buffer)} bytes, "
                f"need {size} (height * line_stride = {self.height} * {self.line_stride})"
            )
        ctypes.memmove(
            (ctypes.c_ubyte * size).from_buffer(buffer),
            self.data_ptr,
            size,
        )

    def as_numpy(self):
        """
        Return a zero-copy NumPy view of the pixel buffer, shape
        ``(height, line_stride // bpp, bpp)``. For BGRA/BGRX/RGBA/RGBX the
        last axis is 4. Slice to ``[:, :width, :]`` if
        ``line_stride > width * bpp`` (line padding).

        Raises ``NotImplementedError`` for non-4-bytes-per-pixel formats
        (UYVY, planar formats etc.) — the SDK can deliver these when the
        receiver is created with ``RECV_COLOR_FASTEST``; in that case prefer
        ``RECV_COLOR_BGRX_BGRA``.

        WARNING: the view is invalidated when this frame is released (the
        ``with`` block exit, or :meth:`release`). Materialise with
        ``np.array(view)`` if you need to keep it around.
        """
        if _np is None:
            raise ImportError("NumPy is required for NDIVideoFrame.as_numpy()")
        bpp = _lib.BYTES_PER_PIXEL.get(self.fourcc)
        if bpp is None:
            raise NotImplementedError(
                f"as_numpy() does not support FourCC 0x{self.fourcc:08x}; "
                "create the receiver with color_format=RECV_COLOR_BGRX_BGRA "
                "or RECV_COLOR_RGBX_RGBA to force a 4-byte-per-pixel format."
            )
        rows = self.height
        cols = self.line_stride // bpp
        raw = (ctypes.c_ubyte * (rows * self.line_stride)).from_address(self.data_ptr)
        return _np.frombuffer(raw, dtype=_np.uint8).reshape(rows, cols, bpp)

    # ------------------------------------------------------------------ #

    def release(self) -> None:
        if self._video is not None and self._recv:
            _lib._dll.NDIlib_recv_free_video_v2(self._recv, ctypes.byref(self._video))
            self._video = None

    def __enter__(self) -> "NDIVideoFrame":
        return self

    def __exit__(self, *_) -> None:
        self.release()

    def __repr__(self) -> str:
        fourcc_chars = self.fourcc.to_bytes(4, "little").decode("ascii", errors="replace")
        return (f"<NDIVideoFrame {self.width}x{self.height} {fourcc_chars} "
                f"stride={self.line_stride} fps={self.fps_n}/{self.fps_d}>")


# --------------------------------------------------------------------------- #
# A "no frame" marker — context-manager-safe, returned when capture times out
# --------------------------------------------------------------------------- #

class _NoFrame:
    """Falsy, context-manager-safe placeholder for ``rx.receive()`` returns
    when no video frame arrived before the timeout."""
    __slots__ = ()
    def __bool__(self): return False
    def __enter__(self): return None
    def __exit__(self, *_): return False
    def __repr__(self): return "<NoFrame>"

_NO_FRAME = _NoFrame()


# --------------------------------------------------------------------------- #
# Receiver
# --------------------------------------------------------------------------- #

class NDIReceiver(_NDIHandle):
    """
    Connect to an NDI sender by name and pull video frames.

    Parameters
    ----------
    source_name : str
        Full NDI source name as advertised on the network, e.g.
        ``"MACHINE-NAME (My Source)"``. The receiver runs an internal finder
        to resolve this to a network endpoint. If the source isn't visible
        within ``connect_timeout_ms`` a :class:`TimeoutError` is raised.
    color_format : int
        One of ``RECV_COLOR_BGRX_BGRA`` (default — 4 bytes/pixel, alpha if
        the sender provides one), ``RECV_COLOR_RGBX_RGBA``,
        ``RECV_COLOR_FASTEST`` (lowest CPU, may pick UYVY — incompatible
        with :meth:`NDIVideoFrame.as_numpy`), or ``RECV_COLOR_BEST``.
    bandwidth : int
        ``RECV_BANDWIDTH_HIGHEST`` (default, full quality) or
        ``RECV_BANDWIDTH_LOWEST`` (proxy preview, much smaller frames).
    recv_name : str
        Local label for this receiver, shown to the sender side.
    allow_video_fields : bool
        If False (default), interlaced sources are de-interlaced into
        single progressive frames before delivery.
    connect_timeout_ms : int
        How long to wait for ``source_name`` to be discovered on the LAN
        before raising ``TimeoutError``. Default 5000 ms.
    """

    _destroy_fn = staticmethod(_lib._dll.NDIlib_recv_destroy)

    def __init__(
        self,
        source_name: str,
        color_format: int = RECV_COLOR_BGRX_BGRA,
        bandwidth: int    = RECV_BANDWIDTH_HIGHEST,
        recv_name: str    = "NDIForPython recv",
        allow_video_fields: bool = False,
        connect_timeout_ms: int  = 5000,
    ):
        super().__init__()
        # Discovery: resolve source_name to an NDIlib_source_t the SDK
        # recognises. Without this, recv_create can fail silently for
        # senders that haven't been seen on the network yet.
        from .finder import NDISourceFinder
        with NDISourceFinder(show_local_sources=True) as finder:
            match = finder.find_source(source_name, timeout_ms=connect_timeout_ms)
        if match is None:
            raise TimeoutError(
                f"NDI source {source_name!r} not found on the network within "
                f"{connect_timeout_ms} ms. Available sources can be listed "
                f"with NDISourceFinder."
            )

        settings = _lib.NDIlib_recv_create_v3_t(
            source_to_connect_to=match,
            color_format=color_format,
            bandwidth=bandwidth,
            allow_video_fields=allow_video_fields,
            p_ndi_recv_name=_lib._to_cstr(recv_name),
        )
        self._instance = _lib._dll.NDIlib_recv_create_v3(ctypes.byref(settings))
        if not self._instance:
            raise RuntimeError("NDIlib_recv_create_v3 returned NULL — failed to create receiver")
        self._source_name = source_name

    # ------------------------------------------------------------------ #

    def receive(self, timeout_ms: int = 33):
        """
        Pull one frame. Returns either an :class:`NDIVideoFrame` (truthy,
        context-manager) or a falsy placeholder if no video arrived in
        ``timeout_ms``.

        Recommended usage::

            with rx.receive(timeout_ms=33) as frame:
                if not frame:
                    continue
                process(frame)         # frame freed automatically on exit

        Note: audio and metadata frames are silently dropped (we pass
        ``NULL`` for those pointers to the SDK so they are never produced).
        """
        video = _lib.NDIlib_video_frame_v2_t()
        ftype = _lib._dll.NDIlib_recv_capture_v2(
            self._instance,
            ctypes.byref(video),
            None,                        # no audio
            None,                        # no metadata
            timeout_ms,
        )
        if ftype == _lib.FRAME_TYPE_VIDEO:
            return NDIVideoFrame(self._instance, video)
        # No frame (timeout / status change / error / etc.) — nothing to free.
        return _NO_FRAME

    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return f"<NDIReceiver source={self._source_name!r} instance={self._instance}>"
