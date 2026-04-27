"""
NDIReceiver — connect to an NDI sender and pull video frames.

Usage::

    from ndi import NDIReceiver

    # Block up to 5 seconds while NDI discovers the source on the LAN.
    with NDIReceiver("MACHINE-NAME (My Source)", connect_timeout_ms=5000) as rx:
        while running:
            with rx.receive(timeout_ms=33) as frame:
                if frame is None:
                    continue
                # frame.width, frame.height, frame.fourcc, frame.data_ptr
                # frame.copy_to(buffer)              — copy into a bytearray
                # frame.as_numpy()                   — zero-copy NumPy view
                process(frame)
"""
import ctypes
import time
from typing import Optional

from . import _lib

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
        ``(height, line_stride // 4, 4)`` for 4-byte pixel formats. Slice to
        ``[:, :width, :]`` if ``line_stride > width * 4``.

        WARNING: the view is invalidated when this frame is released
        (i.e. when the ``with`` block exits or :meth:`release` is called).
        Either copy the data out before release, or call ``np.array(view)``
        to materialise a copy.

        Requires NumPy. Raises ``ImportError`` if NumPy is not installed.
        """
        import numpy as np                                          # local import
        bytes_per_pixel = 4                                          # for BGRA/BGRX/RGBA/RGBX
        rows = self.height
        cols = self.line_stride // bytes_per_pixel
        # ctypes type for an array of (rows * line_stride) bytes at data_ptr.
        ArrayType = (ctypes.c_ubyte * (rows * self.line_stride))
        raw = ArrayType.from_address(self.data_ptr)
        # NumPy view, shape (H, W_padded, 4). Caller can do view[:, :width] to
        # drop any line-stride padding columns.
        return np.frombuffer(raw, dtype=np.uint8).reshape(rows, cols, bytes_per_pixel)

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

class NDIReceiver:
    """
    Connect to an NDI sender by name and pull video frames.

    Parameters
    ----------
    source_name : str
        Full NDI source name as advertised on the network, e.g.
        ``"MACHINE-NAME (My Source)"``. The receiver will run an internal
        finder to resolve this to an actual network endpoint. If the source
        is not visible within ``connect_timeout_ms`` a
        :class:`TimeoutError` is raised.
    color_format : int
        One of ``RECV_COLOR_BGRX_BGRA`` (default — 4 bytes/pixel, alpha if
        the sender provides one), ``RECV_COLOR_RGBX_RGBA``,
        ``RECV_COLOR_FASTEST`` (lowest CPU, may pick UYVY), or
        ``RECV_COLOR_BEST``.
    bandwidth : int
        ``RECV_BANDWIDTH_HIGHEST`` (default, full quality) or
        ``RECV_BANDWIDTH_LOWEST`` (proxy preview, much smaller frames).
    recv_name : str
        Local label for this receiver, shown to the sender side. Defaults
        to ``"NDIForPython recv"``.
    allow_video_fields : bool
        If False (default), interlaced sources are de-interlaced into
        single progressive frames before delivery.
    connect_timeout_ms : int
        How long to wait for ``source_name`` to be discovered on the LAN
        before raising ``TimeoutError``. Default 5000 ms.
    """

    def __init__(
        self,
        source_name: str,
        color_format: int = RECV_COLOR_BGRX_BGRA,
        bandwidth: int    = RECV_BANDWIDTH_HIGHEST,
        recv_name: str    = "NDIForPython recv",
        allow_video_fields: bool = False,
        connect_timeout_ms: int  = 5000,
    ):
        self._instance = None
        # Discovery first — resolve source_name to a NDIlib_source_t the SDK
        # knows about. Without this, recv_create can fail silently for
        # senders that haven't been seen yet.
        from .finder import NDISourceFinder
        match: Optional[_lib.NDIlib_source_t] = None
        deadline = time.monotonic() + connect_timeout_ms / 1000.0
        with NDISourceFinder(show_local_sources=True) as finder:
            while time.monotonic() < deadline and match is None:
                # 200 ms wait per loop — keeps shutdown responsive.
                slice_ms = min(200, max(1, int((deadline - time.monotonic()) * 1000)))
                _lib._dll.NDIlib_find_wait_for_sources(finder._instance, slice_ms)
                count = ctypes.c_uint32(0)
                ptr = _lib._dll.NDIlib_find_get_current_sources(finder._instance, ctypes.byref(count))
                if not ptr or count.value == 0:
                    continue
                wanted = source_name.encode("utf-8")
                for i in range(count.value):
                    if ptr[i].p_ndi_name and ptr[i].p_ndi_name == wanted:
                        # Copy the struct into one we own — the finder's
                        # array is invalidated on the next find call.
                        match = _lib.NDIlib_source_t(
                            p_ndi_name=ptr[i].p_ndi_name,
                            p_url_address=ptr[i].p_url_address,
                        )
                        break
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
            p_ndi_recv_name=recv_name.encode("utf-8"),
        )
        self._instance = _lib._dll.NDIlib_recv_create_v3(ctypes.byref(settings))
        if not self._instance:
            raise RuntimeError("NDIlib_recv_create_v3 returned NULL — failed to create receiver")
        self._source_name = source_name

    # ------------------------------------------------------------------ #

    def receive(self, timeout_ms: int = 33):
        """
        Pull one frame. Returns either an :class:`NDIVideoFrame` (truthy,
        context-manager) or a falsy ``NoFrame`` placeholder if no video
        arrived in ``timeout_ms``.

        Recommended usage::

            with rx.receive(timeout_ms=33) as frame:
                if frame is None:
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
            ctypes.c_uint32(timeout_ms),
        )
        if ftype == _lib.FRAME_TYPE_VIDEO:
            return NDIVideoFrame(self._instance, video)
        # No frame (timeout / status change / error / etc.) — nothing to free.
        return _NO_FRAME

    # ------------------------------------------------------------------ #

    def release(self) -> None:
        if self._instance:
            _lib._dll.NDIlib_recv_destroy(self._instance)
            self._instance = None

    def __enter__(self) -> "NDIReceiver":
        return self

    def __exit__(self, *_) -> None:
        self.release()

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"<NDIReceiver source={self._source_name!r} instance={self._instance}>"
