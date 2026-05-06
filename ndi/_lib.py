"""
Low-level ctypes interface to Processing.NDI.Lib.x64.dll (NDI SDK 5 / 6).

The NDI C API is a flat set of exported functions (no vtable), so binding is
straightforward. We initialize the library once at import time and expose the
relevant structs and function handles.
"""
import atexit
import ctypes
import os
import sys

if sys.platform != "win32":
    raise OSError("NDI is only supported on Windows (Processing.NDI.Lib.x64.dll)")

# --------------------------------------------------------------------------- #
# DLL search
# --------------------------------------------------------------------------- #

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_DLL_NAME = "Processing.NDI.Lib.x64.dll"

# Search order: bundled in this package → env vars → standard install paths.
_search = [os.path.join(_PKG_DIR, _DLL_NAME)]

for _env_key in ("NDI_RUNTIME_DIR_V6", "NDI_RUNTIME_DIR_V5"):
    _env_val = os.environ.get(_env_key)
    if _env_val:
        _search.append(os.path.join(_env_val, _DLL_NAME))

_search += [
    r"C:\Program Files\NDI\NDI 6 Runtime\v6\Processing.NDI.Lib.x64.dll",
    r"C:\Program Files\NDI\NDI 5 Runtime\v5\Processing.NDI.Lib.x64.dll",
    r"C:\Program Files\NDI\NDI 6 SDK\Lib\x64\Processing.NDI.Lib.x64.dll",
    r"C:\Program Files\NDI\NDI 5 SDK\Lib\x64\Processing.NDI.Lib.x64.dll",
]

_dll = None
_dll_path = None
for _p in _search:
    if os.path.exists(_p):
        try:
            _dll = ctypes.CDLL(_p)
            _dll_path = _p
            break
        except OSError:
            pass

if _dll is None:
    raise OSError(
        f"{_DLL_NAME} not found. Install NDI Runtime from https://ndi.video "
        f"or place the DLL next to this file: {_search[0]}"
    )

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# FourCC pixel formats (most common). NDI uses many more; these are enough
# for sender BGRA/RGBA work and receiver BGRX_BGRA mode output.
FOURCC_BGRA = 0x41524742   # b'BGRA' little-endian — 4 bytes/pixel, alpha
FOURCC_BGRX = 0x58524742   # b'BGRX' little-endian — 4 bytes/pixel, alpha ignored
FOURCC_RGBA = 0x41424752   # b'RGBA' little-endian
FOURCC_RGBX = 0x58424752   # b'RGBX' little-endian

# Frame format
FRAME_FORMAT_PROGRESSIVE = 1

# Pass 0 for timecode/timestamp → NDI synthesizes them automatically.

# Receiver color format (NDIlib_recv_color_format_e)
RECV_COLOR_BGRX_BGRA          = 0    # BGRX if no alpha, BGRA if alpha
RECV_COLOR_UYVY_BGRA          = 1
RECV_COLOR_RGBX_RGBA          = 2    # RGBX if no alpha, RGBA if alpha
RECV_COLOR_UYVY_RGBA          = 3
RECV_COLOR_BGRX_BGRA_FLIPPED  = 200
RECV_COLOR_FASTEST            = 100
RECV_COLOR_BEST               = 101

# Receiver bandwidth (NDIlib_recv_bandwidth_e)
RECV_BANDWIDTH_METADATA_ONLY  = -10
RECV_BANDWIDTH_AUDIO_ONLY     = 10
RECV_BANDWIDTH_LOWEST         = 0      # proxy / preview quality
RECV_BANDWIDTH_HIGHEST        = 100    # full-rate video

# Frame type returned by NDIlib_recv_capture_v2
FRAME_TYPE_NONE          = 0
FRAME_TYPE_VIDEO         = 1
FRAME_TYPE_AUDIO         = 2
FRAME_TYPE_METADATA      = 3
FRAME_TYPE_ERROR         = 4
FRAME_TYPE_STATUS_CHANGE = 100

# --------------------------------------------------------------------------- #
# Structs
# --------------------------------------------------------------------------- #

class NDIlib_source_t(ctypes.Structure):
    """An NDI source on the network (returned by find, consumed by recv)."""
    _fields_ = [
        ("p_ndi_name",    ctypes.c_char_p),   # full source name, e.g. "MACHINE (My Source)"
        ("p_url_address", ctypes.c_char_p),   # URL/IP — NULL for sources we create locally
    ]


class NDIlib_find_create_t(ctypes.Structure):
    _fields_ = [
        ("show_local_sources", ctypes.c_bool),  # include sources from THIS machine
        ("p_groups",           ctypes.c_char_p),
        ("p_extra_ips",        ctypes.c_char_p),
    ]


class NDIlib_recv_create_v3_t(ctypes.Structure):
    _fields_ = [
        ("source_to_connect_to", NDIlib_source_t),
        ("color_format",         ctypes.c_int),
        ("bandwidth",            ctypes.c_int),
        ("allow_video_fields",   ctypes.c_bool),
        ("p_ndi_recv_name",      ctypes.c_char_p),
    ]


class NDIlib_send_create_t(ctypes.Structure):
    _fields_ = [
        ("p_ndi_name",  ctypes.c_char_p),   # sender name shown to receivers
        ("p_groups",    ctypes.c_char_p),   # NULL = default group
        ("clock_video", ctypes.c_bool),     # False: don't throttle to video clock
        ("clock_audio", ctypes.c_bool),
    ]


class NDIlib_video_frame_v2_t(ctypes.Structure):
    _fields_ = [
        ("xres",                 ctypes.c_int),
        ("yres",                 ctypes.c_int),
        ("FourCC",               ctypes.c_uint),
        ("frame_rate_N",         ctypes.c_int),    # numerator   (e.g. 60)
        ("frame_rate_D",         ctypes.c_int),    # denominator (e.g. 1)
        ("picture_aspect_ratio", ctypes.c_float),  # 0.0 = xres/yres
        ("frame_format_type",    ctypes.c_int),
        ("timecode",             ctypes.c_int64),  # 0 = synthesize
        ("p_data",               ctypes.c_void_p),
        ("line_stride_in_bytes", ctypes.c_int),    # width * 4 for BGRA/RGBA
        ("p_metadata",           ctypes.c_char_p), # NULL = none
        ("timestamp",            ctypes.c_int64),  # 0 = synthesize
    ]

# --------------------------------------------------------------------------- #
# Function bindings
# --------------------------------------------------------------------------- #

# Library lifecycle
_dll.NDIlib_initialize.restype  = ctypes.c_bool
_dll.NDIlib_initialize.argtypes = []

_dll.NDIlib_destroy.restype  = None
_dll.NDIlib_destroy.argtypes = []

# Sender
_dll.NDIlib_send_create.restype  = ctypes.c_void_p
_dll.NDIlib_send_create.argtypes = [ctypes.POINTER(NDIlib_send_create_t)]

_dll.NDIlib_send_destroy.restype  = None
_dll.NDIlib_send_destroy.argtypes = [ctypes.c_void_p]

_dll.NDIlib_send_send_video_v2.restype  = None
_dll.NDIlib_send_send_video_v2.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(NDIlib_video_frame_v2_t),
]

# Find (mDNS source discovery)
_dll.NDIlib_find_create_v2.restype  = ctypes.c_void_p
_dll.NDIlib_find_create_v2.argtypes = [ctypes.POINTER(NDIlib_find_create_t)]

_dll.NDIlib_find_destroy.restype  = None
_dll.NDIlib_find_destroy.argtypes = [ctypes.c_void_p]

# Returns a pointer to an array of NDIlib_source_t valid until the next call
# to find_get_current_sources or until find_destroy. p_no_sources is filled
# in with the count. The array itself is owned by the finder, do NOT free it.
_dll.NDIlib_find_get_current_sources.restype  = ctypes.POINTER(NDIlib_source_t)
_dll.NDIlib_find_get_current_sources.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]

_dll.NDIlib_find_wait_for_sources.restype  = ctypes.c_bool
_dll.NDIlib_find_wait_for_sources.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

# Receiver
_dll.NDIlib_recv_create_v3.restype  = ctypes.c_void_p
_dll.NDIlib_recv_create_v3.argtypes = [ctypes.POINTER(NDIlib_recv_create_v3_t)]

_dll.NDIlib_recv_destroy.restype  = None
_dll.NDIlib_recv_destroy.argtypes = [ctypes.c_void_p]

# Capture: returns NDIlib_frame_type_e. Pass NULL for the audio / metadata
# pointers if you don't want them (saves NDI work). The pointed-to video
# struct is filled in by NDI; the caller must release it via
# NDIlib_recv_free_video_v2 before the next capture or before recv_destroy.
_dll.NDIlib_recv_capture_v2.restype  = ctypes.c_int
_dll.NDIlib_recv_capture_v2.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(NDIlib_video_frame_v2_t),
    ctypes.c_void_p,                                  # p_audio (unused: NULL)
    ctypes.c_void_p,                                  # p_metadata (unused: NULL)
    ctypes.c_uint32,                                  # timeout_ms
]

_dll.NDIlib_recv_free_video_v2.restype  = None
_dll.NDIlib_recv_free_video_v2.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(NDIlib_video_frame_v2_t),
]

# --------------------------------------------------------------------------- #
# One-time library initialisation
# --------------------------------------------------------------------------- #

if not _dll.NDIlib_initialize():
    raise RuntimeError("NDIlib_initialize() returned False — NDI library failed to start")

# Match the SDK's expected lifecycle: every NDIlib_initialize must be paired
# with NDIlib_destroy. Using atexit avoids relying on __del__ ordering at
# interpreter shutdown.
atexit.register(_dll.NDIlib_destroy)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _to_cstr(s):
    """Encode an optional Python str as UTF-8 bytes for c_char_p, or None."""
    return s.encode("utf-8") if s else None


# Bytes per pixel for the FourCCs we support. Used by NDIVideoFrame.as_numpy
# to refuse unsupported planar/packed formats (e.g. UYVY at 2 bpp).
BYTES_PER_PIXEL = {
    FOURCC_BGRA: 4,
    FOURCC_BGRX: 4,
    FOURCC_RGBA: 4,
    FOURCC_RGBX: 4,
}
